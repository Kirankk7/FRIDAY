#!/usr/bin/env bash
# Set up DVWA in WSL: start MariaDB, create db/user, write config. Serve separately.
set -u
DVWA="/mnt/c/Users/krnkk/DVWA/DVWA-master"

echo "== start mariadb =="
service mariadb start 2>&1 | tail -2 || mysqld_safe --skip-grant-tables &
sleep 4

echo "== create dvwa db + user =="
mariadb -u root <<'SQL'
CREATE DATABASE IF NOT EXISTS dvwa;
CREATE USER IF NOT EXISTS 'dvwa'@'localhost' IDENTIFIED BY 'p@ssw0rd';
CREATE USER IF NOT EXISTS 'dvwa'@'127.0.0.1' IDENTIFIED BY 'p@ssw0rd';
GRANT ALL PRIVILEGES ON dvwa.* TO 'dvwa'@'localhost';
GRANT ALL PRIVILEGES ON dvwa.* TO 'dvwa'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
echo "db exit: $?"

echo "== config.inc.php =="
cd "$DVWA" || { echo "DVWA dir missing"; exit 1; }
cp -f config/config.inc.php.dist config/config.inc.php
sed -i "s/'db_server' ] = '127.0.0.1'/'db_server' ] = '127.0.0.1'/" config/config.inc.php
grep -E "db_server|db_database|db_user|db_password" config/config.inc.php | head -4

echo "== php-mysqli check =="
php -m | grep -i mysqli && echo "mysqli OK" || echo "mysqli MISSING"
echo "SETUP DONE"
