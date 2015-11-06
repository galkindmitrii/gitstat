"""
Defines the routes to operate git repositories, aka /resources/

Supports GET, POST and DELETE methods.

For POST a json holding repository information is required, e.g.
{"url": "https://github.com/galkindmitrii/openstack_swift_s3",
 "branch": "master",
 "revision": "31e695b60cde8149340303d1e282f194128cc676"}
Here url is obligatory, while branch and revision are optional.

For DELETE a json with 'id's of repositories to delete is required:
{"id": [1,2,3,4]}

For GET -> all resources information will be returned by default.
If, however, a list of id's given -> respective resources will be
returned. Lack of 'last_checkout' in repository info means checkout
or clone operation is still in progress.
"""
import fcntl
from os import path, stat
from shutil import rmtree
from time import localtime, strftime

from git import Repo, exc as git_exc
from multiprocessing import Process
from subprocess import check_output
from validators import ValidationFailure, url as url_validator
import simplejson as json  # faster than the std. json

from gitstat import app, redis
from gitstat.errors import BadRequest
from flask import request, make_response, jsonify


# path where git repos will be downloaded to (~/git_repositories/):
GIT_REPOS_PATH = path.join(path.expanduser('~'), "git_repositories/")


@app.errorhandler(BadRequest)
def handle_invalid_usage(error):
    """Handler for BadRequest error."""
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def get_git_repositories():
    """
    HTTP GET /resources handler
    """
    get_req_json = request.get_json(force=True, silent=True)

    if get_req_json:
        try:
            repo_ids = json.loads(get_req_json)
            repo_ids = repo_ids.get('id', [])
        except (KeyError, ValueError) as exc:
            msg = ('An %s Error while decoding request JSON.'
                   % exc)
            app.logger.warning(msg)
            raise BadRequest('Bad Request', 400,
                             {'error': 'Expected a JSON serialized list of '
                              'repository id (-s) to retrieve. '
                              'Or no data to get all.'})
    else:
        # find all resources records:
        repo_ids = redis.keys(pattern='git_repo_id:*')
        if 'git_repo_id:id' in repo_ids:
            repo_ids.remove('git_repo_id:id')

    # create a pipeline to get repos:
    pipe = redis.pipeline()
    for repo_id in repo_ids:
        pipe.hgetall(repo_id)

    # execute a pipeline, collect repos data:
    git_repositories = []
    for repo in enumerate(pipe.execute()):
        repo_dict = {repo_ids[repo[0]]: repo[1]}
        git_repositories.append(repo_dict)

    return make_response(str(git_repositories), 200)


def update_repo_stats(git_repo_id, git_repo_path, git_repo):
    """
    Accumulates the information about 'git_repo_id' repository
    and puts it into DB.
    """
    # real disk usage as 'du' says, faster than 'pythonic' ways of calculation:
    disk_usage = check_output(('du', '-sh',
                               git_repo_path)).split()[0].decode('utf-8')

    # human-readable time format according to rfc2822 e-mail standard:
    checkout_time = strftime("%a, %d %b %Y %H:%M:%S", localtime())

    # get 5 recent commits:
    recent_commits = list(git_repo.iter_commits(max_count=5))

    if recent_commits:  # empty if it's a new 'git init' repo only
        last_author = recent_commits[0].committer
        last_hash = recent_commits[0].binsha.encode('hex')
    else:
        last_author = last_hash = None
    last_msgs = []

    # repository files as in current revision/state.
    all_repo_files = git_repo.git.ls_files().split()

    for commit in recent_commits:
        last_msgs.append(commit.message.encode('utf8', 'ignore'))

    repo_stats = {"recent_committer": last_author,
                  "current_revision": last_hash,
                  "last_5_messages": last_msgs,
                  "total_files": len(all_repo_files),
                  "disk_usage": disk_usage,
                  "last_checkout": checkout_time}

    # update DB record:
    redis.hmset(git_repo_id, repo_stats)


def check_repo_was_cloned(repo_path, repo_id):
    """
    Returns True if in the given 'repo_path' a .git folder
    can be found, it contains a non-empty index file, and
    respective DB record has a 'last_checkout' timestamp.
    """
    path_to_git_index = path.join(repo_path, '.git/index')

    if path.exists(path_to_git_index):
        if stat(path_to_git_index).st_size > 0:
            if redis.hmget(repo_id, 'last_checkout')[0]:
                return True


def run_git_clone_or_checkout(git_repo_id):
    """
    Clones or checks out the repository to 'GIT_REPOS_PATH/'.
    Operations performed with lock to avoid race conditions if
    two users are POSTing the same url at the same time.
    """
    # Get the respective repo url, branch, revision:
    repo_url = redis.hmget(git_repo_id, 'url')[0]
    repo_branch = redis.hmget(git_repo_id, 'branch')[0] or 'master'
    repo_revision = redis.hmget(git_repo_id, 'revision')[0]

    repo_name = repo_url.split('/')[-1]  # assuming url is valid!
    git_repo_path = path.join(GIT_REPOS_PATH, repo_name)  # where to clone
    clone_params = {'branch': repo_branch}  # branch to clone

    with open("".join((repo_name, '.lock')), 'w') as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)  # lock

        try:
            if check_repo_was_cloned(git_repo_path, git_repo_id):
                redis.hdel(git_repo_id, 'last_checkout')  # del last_checkout value
                GitRepo = Repo(git_repo_path)
                GitRepo.git.checkout(repo_branch)

            else:  # otherwise clone the repo:
                GitRepo = Repo.clone_from(repo_url, git_repo_path, **clone_params)

            if repo_revision:  # goto exact commit/revision, if was specified
                GitRepo.git.checkout(repo_revision)

            update_repo_stats(git_repo_id, git_repo_path, GitRepo)

        except (git_exc.CheckoutError, git_exc.InvalidGitRepositoryError,
                git_exc.NoSuchPathError, git_exc.GitCommandError) as exc:
            app.logger.error("Error while git was working: %s" % exc)

        fcntl.flock(lock_file, fcntl.LOCK_UN)  # unlock


def clone_checkout_git_repository(url, repository):
    """
    Creates a new git repository record in the DB;
    Clones the given 'url' by running a separate process.
    """
    url_id_known = redis.get(url)

    if url_id_known:  # repo with this url was already cloned:
        git_repo_id = url_id_known  # use old id, do not create new record
    else:
        # generate next repository ID:
        git_repo_id = ''.join(('git_repo_id:',
                               str(redis.incr('git_repo_id:id'))))
        redis.getset(url, git_repo_id)

    pipe = redis.pipeline()
    pipe.hmset(git_repo_id, repository)
    pipe.execute()

    git_clone_proc = Process(target=run_git_clone_or_checkout,
                             args=(git_repo_id,))
    git_clone_proc.start()  # starts a non-blocking process


def validate_git_url(url):
    """
    Raises error if given repository url is not valid.
    """
    try:
        url_validator(url, True)  # basic check
    except ValidationFailure:
        raise BadRequest('Bad Request', 400,
                         {'error': "The repository url '%s' is not valid."
                         % url})
    # NOTE: a check like 'git ls-remote url' is of course way more robust,
    # but at least with github.com it takes a few seconds sometimes...


def post_git_repositories():
    """
    HTTP POST /resources handler
    """
    post_json = request.get_json(force=True, silent=True)

    if post_json:
        try:
            repository = json.loads(post_json)
            repo_url = repository['url']
        except (KeyError, ValueError) as exc:
            msg = ("An Error while processing incoming JSON Git repository "
                   "information: %s. 'url' is an obligatory parameter." % exc)
            app.logger.warning(msg)
            raise BadRequest('Bad Request', 400, {'error': msg})

        # basic validation if url is correct:
        validate_git_url(repo_url)

        # write to DB and start clone or checkout process:
        clone_checkout_git_repository(repo_url, repository)

        # clone/checkout might not be finished yet
        return make_response('Accepted', 202)

    else:
        # either malformed json or no/not json-serialized data:
        raise BadRequest('Bad Request', 400,
                         {'error': 'Expected a JSON serialized Git '
                          'repository representation with a valid '
                          'remote url with optional [branch, revision]'})


def remove_repos_by_id(repo_ids):
    """
    Try to remove each of the given 'repo_ids':
    Find the url and determine the path.
    If resource exists on the filesystem level ->
    remove its files and DB record.
    """
    for git_repo in repo_ids:
        git_repo_id = ''.join(('git_repo_id:', str(git_repo)))
        repo_url = redis.hmget(git_repo_id, 'url')[0]

        if repo_url:
            repo_name = repo_url.split('/')[-1]  # assuming url is valid!
            git_repo_path = path.join(GIT_REPOS_PATH, repo_name)

            if check_repo_was_cloned(git_repo_path, git_repo_id):
                rmtree(git_repo_path)  # folder on FS
                redis.delete(git_repo_id)  # DB record
                redis.delete(repo_url)  # DB record

            else:
                raise BadRequest('Bad Request', 400,
                                {'error': 'The repository with id %s is '
                                 'not yet cloned.' % git_repo})
        else:
            raise BadRequest('Bad Request', 400,
                            {'error': 'Could not find an url for repository '
                             'with a given id %s. Repository may not exist.'
                             % git_repo})


def delete_git_repositories():
    """
    HTTP DELETE /resources handler
    """
    delete_json = request.get_json(force=True, silent=True)

    if delete_json:
        repo_ids = json.loads(delete_json)
        repo_ids = repo_ids.get('id', [])

        if repo_ids:
            remove_repos_by_id(repo_ids)
            return make_response('OK', 200)
        else:
            raise BadRequest('Bad Request', 400,
                             {'error': 'Expected a JSON serialized list '
                              'of repository id to delete, e.g. id: [1,2,3]'})
    else:
        raise BadRequest('Bad Request', 400,
                         {'error': 'Expected a JSON serialized list '
                          'of repository id (-s) to be deleted.'})


@app.route('/resources/', methods=['GET', 'POST', 'DELETE'])
def get_post_delete_resources():
    """
    Implements an interface to manipulate resources (Git repositories).
    """
    if request.method == 'GET':
        response = get_git_repositories()

    elif request.method == 'POST':
        response = post_git_repositories()

    elif request.method == 'DELETE':
        response = delete_git_repositories()

    else:
        response = make_response('Method Not Allowed', 405)

    return response
