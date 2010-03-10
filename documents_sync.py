#!/usr/bin/env python

# BEEP BEEP THIS module is NOT DONE YET. NOT WORKING.
# BEEP BEEP THIS module is NOT DONE YET. NOT WORKING.
# BEEP BEEP THIS module is NOT DONE YET. NOT WORKING.
# BEEP BEEP THIS module is NOT DONE YET. NOT WORKING.

import os
import sys
import sqlite3
import optparse
import simplejson
import documents_service

UNKNOWN_ID = ""
UNKNOWN_VERSION = -1

parser = optparse.OptionParser(usage="usage: %prog [options]")
parser.add_option("-s", "--host", action="store", dest="host", default="www.simpletext.ws", help="Documents service host URL.")
parser.add_option("-u", "--user", action="store", dest="user", help="Google ID for Google Authentication.")
parser.add_option("-p", "--password", action="store", dest="password", help="Password for Google Authentication.")
parser.add_option("-c", "--service", action="store", dest="service", default="simpletextws", help="Service name for Google authentication.")
options = parser.parse_args()[0]

service_instance = documents_service.DocumentsService(options.host, options.user, options.password, options.service)

class SyncedDocument(object):
	def __init__(self, data):
		self.serverVersion = UNKNOWN_VERSION
		self.name = data.get('name')
		self.content = data.get('content')
		self.shadowID = data.get('id')
		self.shadowVersion = data.get('version')
		self.shadowContent = data.get('content')
	
	def local_edits(self):
		if self.shadowID != None and self.shadowVersion != None:
			edits = {}
			edits['version'] = self.shadowVersion
			if self.content != self.shadowContent:
				edits['patches'] = patches
			return edits
		return None
		
	def has_server_edits(self):
		return self.shadowVersion != self.serverVersion
		
	def isServerDocument(self):
		return self.shadowID != None
	
	def isDeletedFromServer(self):
		pass

	def isInsertedFromServer(self):
		return self.serverVersion != -1 and self.shadowVersion == None

class SyncedDocumentController(object):
	def __init__(self):
		self.documents = []
		
	def sync_document(self, document):
		pass

	def sync_documents(self):
		syncing_documents = []
		
		# 1. Get server documents index, mapped by id
		server_documents_state_by_id = self.read_server_documents_state()

		# 2. Map local documents to server documents
		for each_document in self.documents:
			if each_document.isSyncedToServer():
				each_server_document_state = server_documents_state_by_id[each_document.shadowID]
				if each_server_document_state:
					each_document.serverVersion = each_server_document_state.get('version')
					del server_documents_state_by_id[each_document.shadowID]
					each_document.isDeletedFromServer = False
				else:
					each_document.isDeletedFromServer = True
				syncing_documents.append(each_document)

		# 3. Create new local documents for server documents that don't map. (new ones)
		for each_server_state in server_documents_state_by_id:
			print server_documents_state_by_id[each_server_state]

	def read_server_documents_state(self):
		documents_state_by_id = {}
		for each in service_instance.GET_documents():
			documents_state_by_id[each['id']] = each
		return documents_state_by_id






synced_document_controller = SyncedDocumentController()
synced_document_controller.sync_documents()