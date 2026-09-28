import pymysql

pymysql.install_as_MySQLdb()

# Allow MySQL 8.0.x with Django 6.1
from django.db.backends.base.base import BaseDatabaseWrapper
BaseDatabaseWrapper.check_database_version_supported = lambda self: None
