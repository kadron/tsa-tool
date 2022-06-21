import time, random, docker, os
from collections import Counter

import requests
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

from tsa import Sniffer
from tsa.new_stac import StacPlatform, StacContainer, App

class BidpalApp(App):
	def __init__(self, challengeprogramname, topic, ports):
		self.challengeprogramname = challengeprogramname
		self.topic = topic
		self.ports = ports
		self.params = {}
		self.exptime = time.time()
		self.exptimestamp = self._maketimestamp()
		self.expname = self._makeexpname(self.challengeprogramname, self.topic)
		self.pcapfilename = self._makeoutputfilename('.pcap')
		self.tssfilename = self._makeoutputfilename('.tss')

		self.serverhost = 'serverNuc'
		self.clienthost = 'clientNuc'

		self.servername = 'seller'
		self.clientname = 'buyer'

		self.ports = ports
		self.sniffer = None
		self.run_counter = 0

		self.folder_name = '/data/{}/'.format(self.expname)
		if not os.path.exists(self.folder_name):
			os.makedirs(self.folder_name)

	def launchcontainers(self):
		# Remove any non-registry containers on all hosts
		StacPlatform.cleanuphosts(['clientNuc', 'serverNuc', 'masterNuc'])
		# Launch the server container
		self.server = StacContainer(self.challengeprogramname, self.serverhost)
		self.client = StacContainer(self.challengeprogramname, self.clienthost)

	def startserver(self):
		self.server.container.exec_run("""bash -c 'sed -i "s/Xint/Ddummy=foo/" /home/challenge_program/bin/bidpal'""")
		self.server.container.exec_run("""bash -c 'sed -i "s/Xint/Ddummy=foo/" /home/challenge_program/bin/bidpal.bat'""")
		self.client.container.exec_run("""bash -c 'sed -i "s/Xint/Ddummy=foo/" /home/challenge_program/bin/bidpal'""")
		self.client.container.exec_run("""bash -c 'sed -i "s/Xint/Ddummy=foo/" /home/challenge_program/bin/bidpal.bat'""")

		#Putting our scripts in the container and giving all permissions to read/write/execute
		self.server.execbashcmd('mkdir /home/ourexamples')
		self.client.execbashcmd('mkdir /home/ourexamples')

		#TODO Test this, if it works, it's fine.
		self.server.container.put_archive("/home/ourexamples", \
			open("./bidpal_stuff/scripts.tar","r").read())
		self.client.container.put_archive("/home/ourexamples", \
			open("./bidpal_stuff/scripts.tar","r").read())

		self.server.execbashcmd('chmod 777 /home/ourexamples/*')
		self.client.execbashcmd('chmod 777 /home/ourexamples/*')

	def startsniffer(self):
		print("Starting sniffer")
		self.sniffer = Sniffer(self.ports, showpackets=False)
		self.sniffer.start()

	def stopsniffer(self):
		self.sniffer.stop()

	def export_output(self):
		pass

	def run_inputs(self, inputs, num_samples):
		#TODO This is just original script imported here, we may need to convert dockerclient stuff to StacPlatform abstract version.
		time_started = time.time()

		# Iterate over all instances for each sample number
		for samplenumber in range(num_samples):
			for instance in inputs:
				secret = int(instance.getsecret())

				commstr = """bash -c 'cd /home/ourexamples && sed s/elephant/%d/g auction_buyer_elephant.py > auction_buyer.py'""" % secret
				print("Running secret replacement command:")
				print(commstr)
				self.server.container.exec_run(commstr, stdout=False, detach=True)
				self.client.container.exec_run(commstr, stdout=False, detach=False)

				self.sniffer.newinteraction(str(secret))

				com = "bash -c 'cd /home/ourexamples && python auction_%s.py'" % self.clientname
				print(com)
				self.client.container.exec_run(com, stdout=False, detach=True)
				time.sleep(0.1)

				com = "bash -c 'cd /home/ourexamples && python auction_%s.py'" % self.servername
				print(com)
				self.server.container.exec_run(com, stdout=False, detach=False)
				time.sleep(0.1)

				#print("Ending interaction")

	def finishexperiment(self, end_tag=''):
		self.exptimestamp = self._maketimestamp()
		self.expname = self._makeexpname(self.challengeprogramname, "{}-{}".format(self.topic,end_tag))
		self.pcapfilename = self._makeoutputfilename('.pcap')
		self.tssfilename = self._makeoutputfilename('.tss')

		self.endtime = time.time()
		self.elapsed = self.endtime - self.exptime
		print("\n\nFinishing experiment %s after %.0f seconds\n" % (self.expname, self.elapsed))
		# save time file
		self.saveoutput('%.2f\n' % self.elapsed, '.time')
		self.sniffer.stop()
		#self.sniffer.clean_marked_interactions()

		self.exptimestamp = self._maketimestamp()
		self.pcapfilename = self._makeoutputfilename('.pcap')
		self.tssfilename = self._makeoutputfilename('.tss')
		# save pcap file
		print("Saving " + self.pcapfilename)
		self.sniffer.export(self.pcapfilename)
		# save tss file
		print("Saving " + self.tssfilename)
		self.sniffer.export_tss(self.tssfilename)

		return self.sniffer.interactions

	def removecontainers(self):
		pass
		# Kill and remove the server container
		#self.server.killrm()

	def postfinishexperiment(self):
		# Do some magic analysis here...
		pass
