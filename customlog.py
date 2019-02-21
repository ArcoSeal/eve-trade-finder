import logging

loglevels = {	'debug'		:	logging.DEBUG,
				'info'		:	logging.INFO,
				'warning'	:	logging.WARNING,
				'error'		:	logging.ERROR,
				'critical'	:	logging.CRITICAL
			}

def initlogger(name, loglevel, logfile=None, console=False):
	logFormatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
	customlogger = logging.getLogger(name)
	customlogger.setLevel(loglevels[loglevel])

	if logfile:
		fileHandler = logging.FileHandler(logfile, mode='w')
		fileHandler.setFormatter(logFormatter)
		customlogger.addHandler(fileHandler)

	if console:
		consoleHandler = logging.StreamHandler()
		consoleHandler.setFormatter(logFormatter)
		customlogger.addHandler(consoleHandler)

	return customlogger