import time
from datetime import datetime
from functools import cache
from time import sleep
from typing import BinaryIO

import gridfs
from loguru import logger
from pymongo import MongoClient

from common import schemas
from common.enums import TestRunStatus, AgentEventType
from common.exceptions import MongoConnectionException
from common.schemas import AgentStatusChanged, AgentCompletedBuildMessage, AgentSpecCompleted, AgentSpecStarted, \
    AgentEvent
from common.settings import settings
from common.utils import utcnow


@cache
def client():
    if settings.MONGO_ROOT_PASSWORD:
        return MongoClient(host=settings.MONGO_HOST,
                           username=settings.MONGO_USER,
                           password=settings.MONGO_ROOT_PASSWORD)
    return MongoClient()


@cache
def db():
    return client()[settings.MONGO_DATABASE]


@cache
def runs_coll():
    return db().run


@cache
def specs_coll():
    return db().spec


@cache
def messages_coll():
    return db().message


@cache
def fs():
    return gridfs.GridFS(db())


@cache
def fsbucket():
    return gridfs.GridFSBucket(db())


def get_testrun(testrun_id: int) -> schemas.NewTestRun | None:
    tr = runs_coll().find_one({'id': testrun_id})
    if tr:
        return schemas.NewTestRun.parse_obj(tr)
    return None


def add_message(msg: AgentEvent):
    messages_coll().insert_one({'msg': msg.json()})


def update_status(testrun_id: int, status: TestRunStatus):
    runs_coll().find_one_and_update({'id': testrun_id}, {'$set': {'status': status}})
    add_message(AgentStatusChanged(testrun_id=testrun_id,
                                   type=AgentEventType.status,
                                   status=status))


def check_file_exists(filename: str):
    return fs().exists(filename=filename)


def fetch_file(filename: str, target: BinaryIO):
    fsbucket().download_to_stream_by_name(filename, target)


def store_file(filepath: str, filename: str):
    file = open(filepath, 'rb')
    oid = fsbucket().upload_from_stream(filename, file)
    logger.debug(f'Stored object {str(oid)}')


def get_next_spec(testrun_id: int, pod_name: str = None) -> str | None:
    toset = {'started': datetime.utcnow()}
    if pod_name:
        toset['pod_name'] = pod_name
    s = specs_coll().find_one_and_update({'trid': testrun_id,
                                          'started': None},
                                         {'$set': toset})
    if s:
        add_message(AgentSpecStarted(testrun_id=testrun_id,
                                     type=AgentEventType.spec_started,
                                     started=utcnow(),
                                     file=s['file'],
                                     pod_name=pod_name))
        return s['file']


def set_build_details(testrun: schemas.NewTestRun, specs: list[str], lockhash: str):
    specs_coll().insert_many([{'trid': testrun.id, 'file': f, 'started': None, 'finished': None}
                              for f in specs])
    runs_coll().find_one_and_update({'id': testrun.id}, {'$set': {'status': 'running',
                                                                  'sha': testrun.sha,
                                                                  'cache_key': lockhash}})
    add_message(AgentCompletedBuildMessage(testrun_id=testrun.id,
                                           type=AgentEventType.build_completed,
                                           sha=testrun.sha,
                                           specs=specs,
                                           cache_hash=lockhash))


def spec_completed(testrun: schemas.NewTestRun, spec: str, result: schemas.SpecResult):
    """
    Remove the spec and update the test run
    :return:
    """
    trid = testrun.id
    failures = len([t for t in result.tests if t.error])
    runs_coll().update_one({'id': trid}, {'$inc': {'failures': failures}})
    specs_coll().update_one({'trid': trid, 'file': spec},
                            {'$set': {'finished': datetime.utcnow(),
                                      'result': result.dict()}})
    add_message(AgentSpecCompleted(type=AgentEventType.spec_completed,
                                   testrun_id=trid,
                                   finished=utcnow(),
                                   file=spec,
                                   result=result))


def spec_terminated(trid: int, file: str):
    """
    Make it available again
    :param trid:
    :param file:
    :return:
    """
    specs_coll().update_one({'trid': trid, 'file': file}, {'$set': {'started': None}})


def ensure_connection():
    cl = client()
    if settings.MONGO_ROOT_PASSWORD:
        start = time.time()
        num_nodes = len(cl.nodes)
        while num_nodes < 3:
            logger.info(f"Only {num_nodes} available: waiting...")
            t = time.time() - start
            if t > settings.MONGO_CONNECT_TIMEOUT:
                raise MongoConnectionException()
            sleep(10)
            num_nodes = len(cl.nodes)

            logger.info(f"Connected to MongoDB replicaset")
