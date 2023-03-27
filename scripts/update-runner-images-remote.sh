PWD=`kubectl get secret/cykube-main-mysql --template='{{index .data "mysql-password" | base64decode }}'`
sed "s/TAG/$1/g" scripts/runner-images.sql | mysql -h 127.0.0.1 -u cykube -p$PWD --port 3307 cykubemain
