delete from runnerimage;
insert into runnerimage (node_version, tag, description) values ('16.13.0', 'nickbrookck/cykube-runner:node16.13-TAG', 'Node 16.13');
insert into runnerimage (node_version, tag, description) values ('16.x', 'nickbrookck/cykube-runner:node16.x-TAG',  'Node 16.x');
update project set runner_image = 'nickbrookck/cykube-runner:node16.x-TAG' where runner_image like 'nickbrookck/cykube-runner:node16.x-%';
update project set runner_image = 'nickbrookck/cykube-runner:node16.13-TAG' where runner_image like 'nickbrookck/cykube-runner:node16.13-%';


