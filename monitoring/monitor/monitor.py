########################################################################
# vim: fileencoding=utf-8 ts=8 noexpandtab :
#
# ~~~~ Maiznet.fr ~~~~
#
# Copyright 2011 Grégoire Leroy <gregoire.leroy@retenodus.net>
#
# This file is distributed under the terms of the WTFPL. For more
# informations, see http://sam.zoy.org/wtfpl/COPYING
########################################################################

import config
import socket
from sqlite3 import dbapi2 as sqlite
from datetime import datetime, timedelta

class MonitorProtocol(object):
	"""
	Je gère le protocole de Monitor. Je prend en paramètre l'adresse IP et le port auxquels me connecter.
	"""
	def __init__(self):
		self.ip_server = config.IP_MUNIN
		self.port = config.PORT_MUNIN
		self.connection = sqlite.connect(config.DATABASE)
		self.cursor = self.connection.cursor()

	def fetchValue(self, plugin):
		"""
			Communication avec Monitor-node pour récupérer les valeurs mesurées par un plugin.
		"""
		values = []

		# Création du socket et connexion
		try : 
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.settimeout(3)
			s.connect((self.ip_server,self.port))
		except :
			raise Exception("Échec de l'établisement de la connexion")
		try :
			data = s.recv(4096)
		except :
			raise Exception("Échec de la connexion")

		# Lors de l'établissement d'une connection, Monitor envoie toujours "# Munin node at [host]"
		if "# munin node at" not in data :
			raise Exception("Mauvaises données reçues")

		# Le protocole Munin contient la commande fetch qui permet de récupérer des données
		s.send("fetch %s \r\n" % plugin)
		try : 
			# La fin de la sortie d'une commande se termine toujours par "\n.\n"
			while "\n.\n" not in data :
				data = s.recv(4096)
				data_t = data.split("\n")[0].split(" ")[1]
				values.append(data_t)
		except :
			Exception("No data received")
		s.send("quit\n")
		s.close()
		return values

	def closeDB(self):
		self.connection.commit()
		self.connection.close()
		
class MonitorPlugin(object):
	def __init__(self,plugin,monitorprotocol):
		self.plugin = plugin
		self.mp = monitorprotocol

	def fetchValue(self, function = lambda values : values):
		"""
		Récupère et modifie éventuellement les valeurs
		"""
		self.values = self.mp.fetchValue(self.plugin)
		self.values = function(self.values)
	
	def insertValues(self):
		"""
		Insère les valeurs dans la base de données
		"""
		hours = (datetime.now() - timedelta(hours=config.TIME/60),)
		now = (datetime.now(),)
		self.mp.cursor.execute('INSERT INTO (?) VALUES (null, "(?)", datetime(?))', (self.plugin,), ('", "'.join(self.values),), (now))
		self.mp.cursor.execute('DELETE FROM (?) WHERE datetime(date) <  datetime(?)', (self.plugin,), hours)
	
	def retreiveValues(self):
		""" Utilisé pour les tests uniquement """
		self.mp.cursor.execute('SELECT * FROM if_re1')

def ifacePluginDB(names):
	connection = sqlite.connect(config.DATABASE)
	cursor = connection.cursor()
	for name in names :
		cursor.execute('CREATE TABLE (?) (id INTEGER PRIMARY KEY, `in` INTEGER, out INTEGER, date DATETIME)', (name,))
	connection.commit()
	connection.close()

try :
	rfile = open(config.DATABASE,"r")
	rfile.close()
except:
	ifacePluginDB(config.PLUGINS)

mprot = MonitorProtocol()
for plugin in config.PLUGINS :
	mplug = MonitorPlugin(plugin,mprot)
	mplug.fetchValue(function= lambda values : [str(int(value)/1024) for value in values])
	mplug.insertValues()
mprot.closeDB()
