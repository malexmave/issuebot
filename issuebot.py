import urllib2
import json
import time
import itertools
from wokkel.subprotocols import XMPPHandler
from wokkel.xmppim import AvailablePresence, Presence
from twisted.words.xish import domish
from twisted.internet import reactor
from twisted.python import log

issues = {}
meta = {'RateLimitRemaining' : 60, 'ExceptionCount' : 0}
NS_MUC = 'http://jabber.org/protocol/muc'
NS_XHTML_IM = 'http://jabber.org/protocols/xhtml-im'
NS_XHTML_W3C = 'http://www.w3.org/1999/xhtml'

class IssueBot(XMPPHandler):

    def __init__(self, room, nick, password=None):
        XMPPHandler.__init__(self)

        self.room = room
        self.nick = nick
        self.password = password


    def connectionMade(self):
        self.send(AvailablePresence())
        # join room
        pres = Presence()
        pres['to'] = self.room + '/' + self.nick
        x = pres.addElement((NS_MUC, 'x'))
        if not self.password is None:
            x.addElement('password', content = self.password)
        self.send(pres)
        

    def notify(self, msgt):
        # build the messages
        text = [msgt]
        html = [msgt]
        msg = domish.Element((None, 'message'))
        msg['to'] = self.room
        msg['type'] = 'groupchat'
        msg.addElement('body', content=''.join(text))
        wrap = msg.addElement((NS_XHTML_IM, 'html'))
        body = wrap.addElement((NS_XHTML_W3C, 'body'))
        body.addRawXml(''.join(html))
        # Send message
        self.send(msg)


def pullApi(repo, oauthtoken=None, state='open'):
    # Poll the API and return the JSON-Data and the X-RateLimit-Remaining.
    url = 'https://api.github.com/repos/' + repo + '/issues?state=' + state + "&sort=updated"
    headers = {"User-agent" : "malexmave/Issuebot"}
    if oauthtoken:
        headers["Authorization"] = "token " + oauthtoken
    request = urllib2.Request(url, None, headers)
    response = urllib2.urlopen(request)
    if response.info().getheader('Status') == '200 OK':
        return response.info().getheader('X-RateLimit-Remaining'),  json.load(response)
    else:
        print "[ERR ] Response Code != 200 OK, something's wrong."


def updateMeta(rlimit):
    # Update the remaining Ratelimit information, warn if we approach zero.
    meta['RateLimitRemaining'] = rlimit
    if rlimit <= 5:
        print "[WARN] Approaching rate limit - %i remaining" % (rlimit)



def parseTime(timestring):
    # Convert GitHub-API timestring to UNIX epoch
    tobj = time.strptime(timestring, "%Y-%m-%dT%H:%M:%SZ")
    return time.strftime("%s", tobj)


def newIssueFound(dct, repo):
    # Add a new issue to the database and generate a notification
    log.msg("New Issue found: %s" % (dct['title']))
    tstamp = parseTime(dct['updated_at']) # As UNIX timestamp (epoch)
    issue_no = dct['number']
    issues[repo][issue_no]['title'] = dct['title']
    issues[repo][issue_no]['state'] = dct['state']
    try:
        issues[repo][issue_no]['assignee'] = dct['assignee']['login']
    except TypeError:
        issues[repo][issue_no]['assignee'] = "no one"
    issues[repo][issue_no]['comments'] = dct['comments']
    issues[repo][issue_no]['updated_at'] = tstamp
    issues[repo][issue_no]['url'] = dct['html_url']
    return ["New Issue: \'%s\' (#%i, %s), created by %s, assigned to %s, %i comments. URL: %s" % \
            (dct['title'], issue_no, dct['state'], dct['user']['login'], \
                issues[repo][issue_no]['assignee'], dct['comments'], dct['html_url'])]


def findIssueDelta(dct, repo):
    # Find changes between two versions of an Issue, generating a notification message
    log.msg("Issue updated. Finding changes to %s" % (dct['title']))
    retval = []
    issue_no = dct['number']
    if issues[repo][issue_no]['title'] != dct['title']:
        log.msg("Title changed. Processing")
        rv = "Issue #%i updated: now called \'%s\' (was \'%s\')" % \
            (issue_no, dct['title'], issues[repo][issue_no]['title'])
        retval.append(rv)
        issues[repo][issue_no]['title'] = dct['title']
    if issues[repo][issue_no]['state'] != dct['state']:
        log.msg("State changed. Processing")
        rv = "Issue #%i updated: Issue is now %s (was %s)" % \
            (issue_no, dct['state'], issues[repo][issue_no]['state'])
        retval.append(rv)
        issues[repo][issue_no]['state'] = dct['state']
    try:
        if issues[repo][issue_no]['assignee'] != dct['assignee']['login']:
            log.msg("Assignee changed. Processing")
            rv = "Issue #%i updated: now assigned to %s (was assigned to %s)" % \
                (issue_no, dct['assignee']['login'], issues[repo][issue_no]['assignee'])
            retval.append(rv)
            issues[repo][issue_no]['assignee'] = dct['assignee']['login']
    except TypeError:
        if issues[repo][issue_no]['assignee'] != "no one":
            log.msg("Assignee changed. Processing")
            rv = "Issue #%i updated: now assigned to no one (was assigned to %s)" % \
                (issue_no, issues[repo][issue_no]['assignee'])
            retval.append(rv)
            issues[repo][issue_no]['assignee'] = "no one"
    if issues[repo][issue_no]['comments'] != dct['comments']:
        log.msg("Comments changed. Processing")
        rv = "Issue #%i updated: Gained %i comments (now at %i)" % \
            (issue_no, dct['comments'] - issues[repo][issue_no]['comments'], dct['comments'])
        retval.append(rv)
        issues[repo][issue_no]['comments'] = dct['comments']
    if retval != []:
        rv = "URL to Issue #%i: %s" % (issue_no, dct['html_url'])
        retval.append(rv)
    issues[repo][issue_no]['updated_at'] = parseTime(dct['updated_at'])
    log.msg("All relevant changes to issue have been found. Returning.")
    return retval


def processApiResult(element, repo):
    # Process the API results, creating notification messages
    retval = ""
    new = True
    dct = dict(element)
    issue_no = dct['number']
    try:
        issues[repo][issue_no]
        new = False
    except KeyError:
        issues[repo][issue_no] = {}
    if new:
        retval = newIssueFound(dct, repo)
    else:
        tstamp = parseTime(dct['updated_at']) # As UNIX timestamp (epoch)
        if tstamp > issues[repo][issue_no]['updated_at']: # Issue has updated, act on it
            retval = findIssueDelta(dct, repo)
        else: # Issue has not updated, skip it.
            pass
    return retval


def Initialize(repos, bot, oauth):
    # Initialize database with current data
    for repo in repos:
        issues[repo] = {}
        _, lst_open = pullApi(repo, oauthtoken=oauth)
        rlimit, lst_closed = pullApi(repo, oauthtoken=oauth, state='closed')
        updateMeta(rlimit)
        for element in itertools.chain(lst_open, lst_closed):
            processApiResult(element, repo)


def loop(pTuple):
    try:
        # Poll API and notify the MUC of any changes.
        repos, bot, oauth = pTuple
        for repo in repos:
            _, lst_open = pullApi(repo, oauthtoken=oauth)
            rlimit, lst_closed = pullApi(repo, oauthtoken=oauth, state='closed')
            updateMeta(rlimit)
            messages = []
            for element in itertools.chain(lst_open, lst_closed):
                messages.extend(processApiResult(element, repo))
            if messages != []:
                bot.notify("Updates in repository %s:" % (repo))
            for element in messages:
                bot.notify(element)
            meta['ExceptionCount'] = 0
    except Exception as e:
        meta['ExceptionCount'] += 1
        if meta['ExceptionCount'] < 5 and meta['ExceptionCount'] > 1:
            bot.notify("An Exception occured during the run. Retrying on next cycle for %i more times." % (5 - meta['ExceptionCount']))
            bot.notify("Details: " + str(e))
            log.msg('Error occured: ' + str(e))
        elif meta['ExceptionCount'] == 1:
            log.msg('Error occured for the first time, staying silent.')
            log.msg(str(e))
        else:
            bot.notify('An Exception occured during the run. Five consecutive Exceptions have been reached, stopping execution. Goodbye.')
            bot.notify("Details: " + str(e))
            log.msg('Error occured 5 times in a row, stopping.')
            log.msg(str(e))
            reactor.stop()

