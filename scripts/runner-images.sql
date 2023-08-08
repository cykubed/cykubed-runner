delete from runner_image;
insert into runner_image (node_version, tag, description) values
                         ('16.x', 'europe-docker.pkg.dev/cykubeapp/cykubed/runner-node16.x:TAG',  'Node 16.x');
update project set runner_image = 'europe-docker.pkg.dev/cykubeapp/cykubed/runner-node16.x:TAG' where runner_image like 'europe-docker.pkg.dev/cykubeapp/cykubed/runner-node16.x:%';


