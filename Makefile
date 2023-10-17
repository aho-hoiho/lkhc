VENVDIR=.venv
VENV=. $(VENVDIR)/bin/activate

setup: setup_python setup_web setup_lowkey

setup_python:
#	sudo apt install make emacs-nox
	sudo apt update

#	python
	sudo apt install --yes python3-venv python3-pip python3-dev
	sudo apt install --yes build-essential libssl-dev libffi-dev python3-setuptools jq

	python3 -m venv $(VENVDIR)
	($(VENV); python3 -m pip install --upgrade pip)
	($(VENV); python3 -m pip install -r requirements.txt)

#	mysql
	sudo apt install --yes mysql-server

#	https
	sudo apt install --yes nginx certbot python3-certbot-nginx

#	server
	sudo timedatectl set-timezone `jq -r '.TIMEZONE' instance/config.json`

setup_web:
	cat config/lowkey.nginx | sed -e "s/HOSTNAME/`jq -r '.HOSTNAME' instance/config.json`/g" | sudo tee /etc/nginx/sites-available/lowkey
	sudo rm -f /etc/nginx/sites-enabled/lowkey
	sudo ln -s /etc/nginx/sites-available/lowkey /etc/nginx/sites-enabled
	sudo unlink /etc/nginx/sites-enabled/default
	sudo nginx -t

	sudo ufw allow OpenSSH
	sudo ufw allow 'Nginx Full'

	sudo ufw enable
	sudo certbot run --nginx -d HOST -m EMAIL --agree-tos
#	this modifies /etc/nginx/sites-available/lowkey


setup_mysql:
	sudo systemctl start mysql.service

#	sed -e 's/EOL/\n/g'
	echo "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY ROOTPW" | sed -e "s/ROOTPW/`jq '.MYSQL_ROOT_PASSWORD' instance/secrets.json`/g"| sudo mysql
	echo "CREATE USER 'lkhc'@'localhost' IDENTIFIED BY LKHCPW"  | sed -e "s/LKHCPW/`jq '.MYSQL_LKHC_PASSWORD' instance/secrets.json`/g" | sudo mysql
	echo "GRANT ALL PRIVILEGES ON *.* TO 'lkhc'@'localhost' WITH GRANT OPTION" | sudo mysql
	echo "FLUSH PRIVILEGES;" | sudo mysql
	echo "create database lkhc character set = utf8mb4;" | sudo mysql

	sudo systemctl status mysql.service
	sudo mysql_secure_installation --password=`jq -r '.MYSQL_ROOT_PASSWORD' instance/secrets.json` -D
	sudo mysqladmin -p -u lkhc version
#	mysql -p -u lkhc

setup_lowkey:
	sudo cp config/lowkey.service /etc/systemd/system/lowkey.service
	sudo systemctl enable lowkey.service
	sudo systemctl start lowkey.service
	sudo chgrp www-data /home/ubuntu

	sudo mkdir -m 755  -p /var/log/lowkey
	sudo chown root:www-data /var/log/lowkey
	sudo touch /var/log/lowkey/lowkey.log
	sudo chown ubuntu:www-data /var/log/lowkey/lowkey.log
	sudo cp config/lowkey.logrotate  /etc/logrotate.d/lowkey
