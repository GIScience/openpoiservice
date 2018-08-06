bind = "0.0.0.0:5000"
# Generally we recommend (2 x $num_cores) + 1 as the number of workers to start off with
workers = 4
worker_class = 'gevent'
worker_connections = 1000
timeout = 30
keepalive = 2
