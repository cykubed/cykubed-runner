import pytest


@pytest.fixture
def testrun():
    return {
            "id": 100,
            "branch": "master",
            "sha": "sha",
            "project": {
                "id": 40,
                "name": "dummy",
                "platform": "github",
                "url": "git@github.com:nickbrook72/dummyui.git",
                "parallelism": 4,
                "build_cmd": "ng build",
                "server_cmd": "ng serve",
                "server_port": 4200,
            },
            "total_files": 2,
            "completed_files": 0,
            "progress_percentage": 0,
            "status": "running",
            "started": "2022-05-01T15:00:12",
            "active": True
        }
