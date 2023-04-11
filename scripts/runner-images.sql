delete from runnerimage;
insert into runnerimage (node_version, tag, description) values
                         ('16.x', 'europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-node16.x:TAG',  'Node 16.x');
update project set runner_image = 'europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-node16.x:TAG' where runner_image like 'europe-west2-docker.pkg.dev/cykubeapp/cykube/runner-node16.x:%';


