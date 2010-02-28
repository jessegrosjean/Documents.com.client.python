#!/usr/bin/env python

import os
import sys
import simplejson
import diff_match_patch
import documents_service_support

"""
	Client script for reading/writing documents hosted by the open source "Documents.com" service:
	
		http://github.com/jessegrosjean/Documents.com.client.python
	
	Note that WriteRoom.iPhone's document sharing feature works by starting a simplifiled
	"Documents.com" web server. That means that you can also use this script to automate reading
	and writing of documents from WriteRoom.iPhone when document sharing is turned on.
	
	Example:
	
		service = DocumentsService("simpletextws", "www.simpletext.ws", "your_google_account_email", "your_pass")
		print service.GET_documents()
		
	URL's:
	
		GET /v1/documents
		POST /v1/documents
		GET /v1/documents/<document_id>
		PUT /v1/documents/<document_id>
		DELETE /v1/documents/<document_id>
		GET /v1/documents/<document_id>/revisions
		GET /v1/documents/<document_id>/revisions/<revision_id>
		DELETE /v1/documents/<document_id>/revisions/<revision_id>
		
	
"""
class DocumentsService(object):
	def __init__(self, host, user, password, source="ws.simpletext.python.client", account_type=None):
		self.server = documents_service_support.HttpRpcServer(host, lambda: (user, password), documents_service_support.GetUserAgent(), source, save_cookies=True, account_type=account_type)
	
	""" Get index list of server documents.

		Returns:
			Array of dictionaries. Each with the keys: id, version, name
	"""
	def GET_documents(self):
		return simplejson.loads(self.server.Send("/v1/documents"))

	""" Post new document.

		Args:
			name: New document's name
			content: New document's content
		Returns:
			New document's server state.
	"""
	def POST_document(self, name, content):
		return simplejson.loads(self.server.Send("/v1/documents", body=simplejson.dumps({ "name" : name, "content" : content })))

	""" Get server document.

		Args:
			id: Document's id
		Returns:
			Document dictionary with the keys: id, version, name, content
	"""
	def GET_document(self, id):
		return simplejson.loads(self.server.Send("/v1/documents/%s" % id))

	""" Update server document. Updates to document content are intended to be done by sending patches.
		To create the patch the client should keep track of the last known content from the server, and then
		they should do a diff between that, and the new content that the user has created.
		
		Sending patches has two advantages. They save network bandwidth, since the entire document doesn't need
		to be sent to the server. Second they enable the server to easily merge changes from more then one source
		so that data doesn't get overwriten.

		Args:
			id: Document's id
			version: Local version of the document.
			name: New name for document.
			patches: Patches that will be applied to server document's content.
			content: If no patches are provided you can set the content directly, but this is expensive
			and will overwrite changes on the server.
		Returns:
			Document's new state on server after applying your changes.
			May also include a 'conflicts' key if there were conflicts.
	"""
	def PUT_document(self, id, version, name=None, patches=None, content=None):
		body = {}
		if version: body['version'] = version
		if name: body['name'] = name
		if patches:
			body['patches'] = patches
		elif content:
			dmp = diff_match_patch.diff_match_patch()
			server_content = self.GET_document(id)['content']
			body['patches'] = dmp.patch_toText(dmp.patch_make(server_content, content))	
		return self.server.Send("/v1/documents/%s" % id, body=simplejson.dumps(body), method="PUT")

	""" Delete document.

		Args:
			id: Document's id
			version: Documents version. Must match current version on server for delete to succeed.
	"""
	def DELETE_document(self, id, version):
		return self.server.Send("/v1/documents/%s?version=%i" % (id, version), method="DELETE")

	""" Get document revisions. Note, this only works for python Google App Engine server.
		The server built into TaskPaper and WriteRoom apps doens't support revisions.

		Args:
			document_id: Document's id
		Returns:
			Keys for each saved revision of the document.
	"""
	def GET_document_revisions(self, document_id):
		return simplejson.loads(self.server.Send("/v1/documents/%s/revisions" % document_id))

	""" Get document revision. Note, this only works for python Google App Engine server.
		The server built into WriteRoom.iPhone doens't support revisions.

		Args:
			document_id: Document's id
			revision_id: Revision's id
		Returns:
			Revisions dictionary with keys id, version, name, content
	"""
	def GET_document_revision(self, document_id, revision_id):
		return simplejson.loads(self.server.Send("/v1/documents/%s/revisions/%s" % (document_id, revision_id)))
		
	""" Delete document revision. Note, this only works for python Google App Engine server.
		The server built into WriteRoom.iPhone doens't support revisions.

		Args:
			document_id: Document's id
			revision_id: Revision's id
	"""
	def DELETE_document_revision(self, document_id, revision_id):
		return self.server.Send("/v1/documents/%s/revisions/%s" % (document_id, revision_id), method="DELETE")