#!/bin/bash

APITOKEN=$(mysql -sNe "select token from user limit 1" cykubedmain)
http POST http://localhost:5002/admin/docker/image -A bearer -a $APITOKEN  < dockerfiles/generated/full/cykubed-payload.json

