#!/usr/bin/env python

import os
import sys
import logging
import sqlite3
import optparse
import simplejson
import diff_match_patch
import documents_service

UNKNOWN_ID = ""
UNKNOWN_VERSION = -1

"""
	Sync model for syncing documents hosted by the open source "Documents.com" service to local state:
	
		http://github.com/jessegrosjean/Documents.com.client.python
	
	Note that WriteRoom and TaskPaper for iPhone's document sharing feature works by starting a simplifiled
	"Documents.com" web server. That means that you can also use this model to sync documents directly from WriteRoom
	or TaskPaper for iPhone when document sharing is turned on.
	
	Example:
	
		import logging
		import documents_service
		import documents_controller
		logging.basicConfig(level=logging.INFO)
		controller = documents_controller.DocumentController(documents_service.DocumentsService("www.simpletext.ws", "google_id", "google_pass", "simpletextws"))
		controller.sync_documents()
		
		# At this point server state is synced down. Try calling sync_documents() again and note that the response is much
		# faster (assuming you had documents on the server the first time around) because there are no changes to sync.
		controller.sync_documents()
		
		# Try making a change on the server and then call sync_documents() again, that change is synced down.
		controller.sync_documents()
		
		# Change some local state and sync again, then look at web server, document on server should also be updated.
		controller.documents[0].content = "new content"
		controller.sync_documents()
"""

class Document(object):
	def __init__(self, data):
		self.server_version = UNKNOWN_VERSION
		self.name = data.get('name')
		self.tags = data.get('tags')
		self.user_ids = data.get('user_ids')
		self.content = data.get('content')
		self.shadow_id = data.get('id', UNKNOWN_ID)
		self.shadow_version = data.get('version')
		self.shadow_tags = data.get('tags')
		self.shadow_name = data.get('name')
		self.shadow_user_ids = data.get('user_ids')
		self.shadow_content = data.get('content')
		self.is_deleted_from_server = False
		self.is_deleted_from_client = False
	
	def __str__( self ):
		return "%s %s %s" % (self.name, self.shadow_id, self.shadow_version)
		
	def local_edits(self):
		if self.shadow_id != None and self.shadow_version != None:
			edits = { 'version' : self.shadow_version }

			if self.name != self.shadow_name:
				edits['name'] = name

			if self.content != self.shadow_content:
				dmp = diff_match_patch.diff_match_patch()
				edits['patches'] = dmp.patch_toText(dmp.patch_make(self.shadow_content, self.content))	
				
			if self.tags != self.shadow_tags:
				edits['tags_added'] = filter(lambda tag: tag not in self.shadow_tags, self.tags)
				edits['tags_removed'] = filter(lambda tag: tag not in self.tags, self.shadow_tags)

			if self.user_ids != self.shadow_user_ids:
				edits['user_ids_added'] = filter(lambda tag: tag not in self.shadow_user_ids, self.user_ids)
				edits['user_ids_removed'] = filter(lambda tag: tag not in self.user_ids, self.shadow_user_ids)
				
			if len(edits) > 1:
				return edits
				
		return None
	
	def has_local_edits(self):
		return self.local_edits() != None
		
	def has_server_edits(self):
		return self.shadow_version != self.server_version
		
	def is_server_document(self):
		return self.shadow_id != UNKNOWN_ID
	
	def is_inserted_from_server(self):
		return self.server_version != UNKNOWN_VERSION and self.shadow_version == None

	def GET(self, controller):
		logging.info("GETTING: %s", self)
		return self.handle_sync_response(controller.rest_service.GET_document(self.shadow_id), controller)

	def PUT(self, controller):
		logging.info("PUTTING: %s", self)
		edits = self.local_edits()
		return self.handle_sync_response(controller.rest_service.PUT_document(
			self.shadow_id, 
			self.shadow_version,
			name=edits.get('name'),
			tags_added=edits.get('tags_added'),
			tags_removed=edits.get('tags_removed'),
			user_ids_added=edits.get('user_ids_added'),
			user_ids_removed=edits.get('user_ids_removed'),
			patches=edits.get('patches')), controller)

	def POST(self, controller):
		logging.info("POSTING: %s", self)
		return self.handle_sync_response(controller.rest_service.POST_document(self.name, tags=self.tags, user_ids=self.user_ids, content=self.content), controller)

	def DELETE(self, controller):
		logging.info("DELETEING: %s", self)
		return self.handle_sync_response(controller.rest_service.DELETE_document(self.shadow_id, self.shadow_version), controller)

	def sync(self, controller):
		# Handle delete cases.
		if self.is_deleted_from_server:
			if self.has_local_edits():
				self.is_deleted_from_server = False
				return self.POST(controller)
			else:
				controller.delete_document(self)
				return None
		elif self.is_deleted_from_client:
			if self.has_server_edits():
				self.is_deleted_from_client = False
				return self.GET(controller)
			else:
				return self.DELETE(controller)

		# Handle create cases.
		if not self.is_server_document():
			return self.POST(controller)
		elif self.is_inserted_from_server():
			return self.GET(controller)

		# Handle changes.
		if self.has_local_edits():
			return self.PUT(controller)
		elif self.has_server_edits():
			return self.GET(controller)

		return None
		
	def handle_sync_response(self, response, controller):
		if self.is_deleted_from_client:
			controller.delete_document(self)
			return None
		
		if response.get('id'): self.shadow_id = response['id']
		if response.get('version', None): # 'version' can be zero, need that case to pass test, so passing in None, not sure if this is best way.
			self.shadow_version = response['version']
			self.server_version = self.shadow_version
			
		if response.get('name'):
			self.shadow_name = response['name']
			self.name = self.shadow_name
		if response.get('tags'):
			self.shadow_tags = response['tags']
			self.tags = self.shadow_tags
		if response.get('user_ids'):
			self.shadow_user_ids = response['user_ids']
			self.user_ids = self.shadow_user_ids
		if response.get('content'):
			self.shadow_content = response['content']
			self.content = self.shadow_content
			
		controller.updated_document(self)
			
		if response.get('conflicts'):
			return response['conflicts']
		else:
			return None

class DocumentController(object):
	def __init__(self, rest_service):
		self.documents = []
		self.rest_service = rest_service
		
	""" Get user visible documents, all locally stored documents that are not
		scheduled for delete on the server (is_deleted_from_client).
	"""
	def client_visible_documents(self):
		return filter(lambda document: not document.is_deleted_from_client, self.documents)

	""" Create document from clients perspective. Sync will need to be performed to POST document
		to server, or GET document state from server.
	"""
	def client_create_document(self, data=None):
		document = Document(data)
		self.documents.append(document)
		logging.info("Created: %s", document)
		return document
	
	""" Delete document from clients perspective. If the document has never been synced to server
		then delete immediatly. If it has been searched set is_deleted_from_client so that it will
		no longer show up in client_visible_documents and so that it will be deleted from server on next sync.
	"""
	def client_delete_document(self, document):
		if document.is_server_document():
			document.is_deleted_from_client = True
			logging.info("Scheduled Delete: %s", document)
		else:
			self.delete_document(document)

	def updated_document(self, document):
		logging.info("Updated: %s", document)
		
	def delete_document(self, document):
		self.documents.remove(document)
		logging.info("Deleted: %s", document)
	
	""" Sync client state with server. Note, server model doesn't handle many document sync requests at the same
		time. So as in this example... each document sync needs to be performed synchronously. This will be fixed
		on the server on a future date.
	"""
	def sync_documents(self):
		syncing_documents = []
		
		# 1. Get server documents index (id, version, name), mapped by id
		server_documents_index_by_id = {}
		for each_server_document_index in self.rest_service.GET_documents():
			server_documents_index_by_id[each_server_document_index['id']] = each_server_document_index

		# 2. Map local documents to server documents, and tag local documents that are deleted from server.
		for each_document in self.documents:
			if each_document.is_server_document():
				each_server_document_index = server_documents_index_by_id.get(each_document.shadow_id)
				if each_server_document_index:
					each_document.server_version = each_server_document_index.get('version')
					del server_documents_index_by_id[each_document.shadow_id]
					each_document.is_deleted_from_server = False
				else:
					each_document.is_deleted_from_server = True
				syncing_documents.append(each_document)

		# 3. Create new local documents for server documents that don't map. (new ones)
		for each_server_document_index_id in server_documents_index_by_id:
			each_document = self.client_create_document(server_documents_index_by_id[each_server_document_index_id])
			syncing_documents.append(each_document)

		# 4. Sync each document
		for each_document in syncing_documents:
			conflicts = each_document.sync(self)
			if conflicts:
				logging.warn("%s conflicts: %s" % (each_document, conflicts))