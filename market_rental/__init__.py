# Use PyMySQL as the MySQL driver. Django's MySQL backend expects the
# `MySQLdb` module, so register PyMySQL's drop-in shim before Django loads.
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover - driver only needed for MySQL setups
    pass
