#I separate title text and body text. I then make each occurance of title text
#count for 2x body text. I made a class to store the counts for each and it can 
#be extended for other types of text too.

from bs4 import BeautifulSoup, Comment

from xml.etree import ElementTree

import os
import re
import sys
import time

import urllib.parse
import urllib.request
import urllib.robotparser

import webbrowser

#class for storing index results
class IndexObj(object):
	def __init__(self,pid,url,title,text):
		self.id = pid
		self.url = url
		self.title = title
		self.text = text

#separated robot; although only used for ischool domain, if it were used for others, 
#a seperate class would allow for the creation of different robots.
class Robot(object):
	def __init__(self,uri):
		self.rp = urllib.robotparser.RobotFileParser()
		self.rp.set_url(uri + '/robots.txt')
		self.rp.read()

	# returns True if it is ok to fetch this url, else False
	def OKToCrawl(self, url):
		return self.rp.can_fetch("*", url)

#crawls and finds links and creates the index
class Crawler(object):
	urlQ = []
	urlC = []
	indexList = {}

	def __init__(self, startURL):
		req = urllib.request.Request(startURL)
		self.uriHost = req.host 	 		#returns www.ischool.berkeley.edu
		self.uriBase = '{}://{}'.format(req.type,self.uriHost)  #constructs http://www.ischool.berkeley.edu/
		directory = req.selector
	
		self.robot = Robot(self.uriBase)
		if self.robot.OKToCrawl(directory):
			self.urlQ.append(startURL)
		else:
			print('Starting URL is Disallowed')
		
	def crawl(self,stopAfter):
		while self.urlQ:
			self.RequestResponse()

			if self.response:
				self.pageIndexer()

				#add links to queue
				self.linkQuerer()
			
			self.urlC.append(self.urlQ.pop(0))
			print('Crawled: ' + self.urlC[-1])
			# print(self.indexList)
			# print(urlQ)
			if len(self.urlC) == stopAfter:
				break
			time.sleep(1)

	def RequestResponse(self):
		try:
			self.response = urllib.request.urlopen(self.urlQ[0])
		except urllib.error.URLError as err:
			print("Error opening url {} .\nError is: {}".format(url, err))
			self.response = False

	# extract all the links (‘a’ tags) from a web page
	def linkQuerer(self):
		for link in self.soup.find_all('a'):
			link = link.get('href')
			if link is not None:
				if link[0] == '/':
					if self.robot.OKToCrawl(link):
						self.appendQ(self.completeURL(link))
					else:
						print('Skipped: ' + link)
				elif link[0:4] == 'http' or link[0:3] == 'www':
					#get domain
					# print(link)
					linkHost = urllib.request.Request(link).host
					if linkHost is not None:
						#It only crawls web pages within the ischool.berkeley.edu domain.  It should check to be sure that no pages it accesses are outside this domain.
						#disallows https types (which one assumes requires PW) such as wiki
						if urllib.request.Request(link).type != 'https':
							#removes the first part of url such as blogs or www to compare link domain to base crawler domain:
							#checks for lazy url, so 'ischool.berkeley.edu' will compare to www.ischool.berkeley.edu
							#end result: allows courses and blogs, etc; disallow non-ischool domains 
							if linkHost.split('.',1)[1] == self.uriHost.split('.',1)[1] or linkHost == self.uriHost.split('.',1)[1]:
								#if we were allowing non-ischool domain, would need to create new robot instances to check robot files on new domain.
								#since we are not and the above filter should get rid of non-ischool domains, just comapre directory to robot
								#parse to get path and check agains robot
								directory = urllib.parse.urlparse(link)
								if self.robot.OKToCrawl(directory.path):
									self.appendQ(link)
								#dumbass....
								# directory = re.search(r"[\w+://\.]?[www\.]?[\w+\.]+[\w+](/[\w\./\-_]+)" ,link, re.IGNORECASE)
								##if re successful, check the robot file
								# if directory:
								#	if self.robot.OKToCrawl(directory.group(1)):
								#		self.appendQ(link)
								##if not, then it means it is a domain with no directory, so we can just add
								# else:
								# 	self.appendQ(link)
								else:
									print('Skipped: ' + link)
							else:
								print('Skipped: ' + link)
						else:
							print('Skipped: ' + link)
					else:
						print('Skipped: ' + link)
				else:
					print('Skipped: ' + link)

	#add full path to a relative link
	def completeURL(self,onpage_url):
		return urllib.parse.urljoin(self.uriBase,onpage_url)

	#appends unique links
	def appendQ(self,link):
		#It should avoid loops.
		#if not in queue or completed list
		#it does include things which it should not crawl. Will get checked later; kinda silly but too lazy to fix
		if link not in self.urlQ and link not in self.urlC:
			self.urlQ.append(link)

	#page indexer
	def pageIndexer(self):
		self.soup = BeautifulSoup(self.response.readall())
		self.cleanText()
		docText = self.soup.body.get_text()
		#creates an IndexObj object as declared above
		temp = IndexObj(len(self.urlC),self.response.geturl(),self.soup.find('title').text,re.sub(r'\n\s+',r'\n',docText))
		#creates dic of these objects with the url id as key
		self.indexList[temp.id] = temp
		# print("id: {}".format(self.indexList[temp.id].id))
		# print("url: {}".format(self.indexList[temp.id].url))
		# print('title: ' + self.indexList[temp.id].title)
		# print("text: {}".format(self.indexList[temp.id].text))

	#cleans text of comments and scripts
	def cleanText(self):
		comments = self.soup.body.find_all(text=lambda text:isinstance(text, Comment))
		[comment.extract() for comment in comments]
		tags = self.soup.body.find_all('script')
		[tag.extract() for tag in tags]

#class for word counts for each site
class Doc(object):
	def __init__(self,pid,tc,bc):
		self.id = pid
		self.titleCount = tc
		self.bodyCount = bc
		# self.totalCount = (tc * 2) + bc

#function to cycle through crawler index text and create a dic of word:Doc
def findWords(dic,pid,pageText,bool):
	pageText = pageText.split()
	for word in pageText:
		word = word.strip('[]{}\\|;:\'",./<>?!`~@#$%^&*()_+-=1234567890')
		word = word.lower()
		if word != '':
			if word in dic:
				# inelegant; too lazy to figure out a better way to differentiate between titles and body
				#this entire thing is a little clunky. would need to rework my two classes to make it less so...
				if pid in dic[word].keys():
					if bool:
						dic[word][pid].bodyCount += 1
					else:
						dic[word][pid].titleCount += 1
				else:
					if bool:
						dic[word][pid] = Doc(pid,0,1)
					else:
						dic[word][pid] = Doc(pid,1,0)
			else: 
				if bool:
					dic[word] = {pid:Doc(pid,0,1)} 
				else:
					dic[word] = {pid:Doc(pid,0,1)} 

#function for finding comment elements in two lists; used after query search
def intersect(a, b):
     return list(set(a) & set(b))

#tester function
def returnResults(term, termIndex, crawlIndex):
	try:
		for key,val in termIndex[term].items():
			print('site id: {}'.format(key))
			print('term count in title: {}'.format(val.titleCount ))
			print('term count in body: {}'.format(val.bodyCount ))
			print('cross reference with site index:')
			print('site url: ' + crawlIndex[key].url)
			print('site title text: ' + crawlIndex[key].title)
			print('site body text: ...{}...'.format(crawlIndex[key].text[1750:2250]))
			print('\n\n')
	except KeyError:
		print('Term {} not found in any of the crawled sites'.format(term))

#function to determine rank of page; title word counts for 2x body
def nahmanRank(docs,terms,index):
	dic = {}
	for docID in docs:
		count = 0
		for term in terms:
			count = (index[term.lower()][docID].titleCount * 2) + index[term.lower()][docID].bodyCount
		if count in dic:
			dic[count].append(docID)
		else:
			dic[count] = [docID]
	return dic

#creates html elements
def createHTML(query):
	html = ElementTree.Element('html')
	head = ElementTree.SubElement(html, 'head')
	body = ElementTree.SubElement(html, 'body')

	title = ElementTree.SubElement(head, 'title')
	title.text = 'Eloogle'
	ElementTree.SubElement(head, 'link', attrib = {'href':'search.css','rel':'stylesheet','type':'text/css'})

	titleSection = ElementTree.SubElement(body, 'section')
	titleH1 = ElementTree.SubElement(titleSection, 'h1')
	section = ElementTree.SubElement(body, 'section', attrib = {'class':'queryTitle'})
	span = ElementTree.SubElement(section, 'span', attrib = {'class':'query'})
	
	titleH1.text = 'Eloogle'
	section.text = "Query: "
	span.text = query

	return html,body

def addSearchResults(body,title,url,text):

	section = ElementTree.SubElement(body, 'section', attrib = {'class':'result'})
	titleDiv = ElementTree.SubElement(section, 'h2', attrib = {'class':'title'})
	urlDiv = ElementTree.SubElement(section, 'a', attrib = {'href':url, 'target':'_blank'})
	textDiv = ElementTree.SubElement(section, 'p', attrib = {'class':'text'})

	titleDiv.text = title
	urlDiv.text = url
	textDiv.text = text

def failedResult(body):
	section = ElementTree.SubElement(body, 'section', attrib = {'class':'fail'})
	section.text = "Sorry, query terms were not found in the documents"

def termFailResult(body,terms):
	fail = ElementTree.SubElement(body, 'section',attrib = {'class':'fail'})
	fail.text = 'The term(s) "{}" were not found.'.format(' '.join(terms))
	section = ElementTree.SubElement(body, 'section')
	section.text = "Results for the rest of your query terms:"

def main():
	searchIndex = {}

	ischool = Crawler('http://www.ischool.berkeley.edu/courses/2012/spring')
	ischool.crawl(40)

	for page in ischool.indexList:
		findWords(searchIndex,ischool.indexList[page].id,ischool.indexList[page].title,0)
		findWords(searchIndex,ischool.indexList[page].id,ischool.indexList[page].text,1)

		#searchIndex stored as dictionary & objects in json-esque format. 
		#searchIndex = {
		#		'word': Documents{
		#							0:Doc{
		#								id:int, 
		#								titleCount:int, 
		#								bodyCount:int
		#							}
		#							1:Doc, etc
		#	  				},
		#		'word2': Documents{
		#							0:Doc,
		#							1:Doc, etc
		#	  				}
		#}

		#CrossReference above with ischool.indexList by .id
		#.indexList = IndexObj{
		#		id: {
		#			id:int,		
		#			url:string,
		#			title: string,	//short string
		#			text: string  	//very long string; need to figure out a good section to display
		#		}
		#}
	
	while 1:
		docList = []
		failedTerms = []
		sucessfulTerms = []
		docCount = {}
		failed = False

		query = input("\n(e) to exit or enter query: \n")
		if query == 'e':
			break
		queryTerms = query.split()
		docList = list(ischool.indexList.keys())
		while queryTerms:
			try:
				termDocs = list(searchIndex[queryTerms[0].lower()].keys())
				docList = intersect(termDocs,docList)
				sucessfulTerms.append(queryTerms.pop(0))

			except KeyError:
				print('Term "{}" not found in any of the crawled sites'.format(queryTerms[0]))
				failedTerms.append(queryTerms.pop(0))
				failed = True

		#create base html elements once; everything else references these
		html,body = createHTML(query)

		if sucessfulTerms:
			docCount = nahmanRank(docList,sucessfulTerms,searchIndex)

			if failed:
				print("Results for the rest of your query terms:")
				termFailResult(body,failedTerms)
			
			keys = list(docCount.keys())
			keys.sort()
			keys.reverse()
			for key in keys:
				for site in docCount[key]:
					addSearchResults(body,ischool.indexList[site].title,ischool.indexList[site].url,ischool.indexList[site].text[1750:2250])
					print('\n')
					print('site title text: ' + ischool.indexList[site].title)
					print('site url: ' + ischool.indexList[site].url)
					print('site body text: ...{}...'.format(ischool.indexList[site].text[1750:2250]))
					print('\n')

		else:
			failedResult(body)
			print("Sorry, query terms were not found in the documents")

		ElementTree.ElementTree(html).write('search_results.html')
		abs_path = os.path.abspath('.')
		filename = os.path.join(abs_path, "search_results.html")
		print(filename)
		webbrowser.open('file://'+filename)

if __name__ == '__main__':
	main()