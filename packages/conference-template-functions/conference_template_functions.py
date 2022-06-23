from lektor.pluginsystem import Plugin
from lektor.context import site_proxy, get_ctx
import csv
import os
from collections import defaultdict

from werkzeug.urls import url_parse
from markupsafe import escape

NOFOLLOW_LINK_PREFIX = '!'

import sys


if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')
else:
    unicode = str

def get_drive_url(path):
    drive_paths = site_proxy.databags.get_bag('drivepaths')
    p = path
    if '/seminarContent' in path and not path.startswith('/seminarContent/'):
        p = p[p.find('/seminarContent'):]

    if '/seminarContent' in path and p not in drive_paths:
        raise ValueError("Path not in Google Drive: {}".format(p))
    elif '/seminarContent' not in path and p not in drive_paths:
        return p

    ident = drive_paths[p]

    return "https://drive.google.com/file/d/{}/view?usp=sharing".format(ident)

class LinkMixin(object):
    def link(self, link, title, text):
        nofollow = link.startswith(NOFOLLOW_LINK_PREFIX)
        link = link.lstrip(NOFOLLOW_LINK_PREFIX)
        
        if self.record is not None:
            url = url_parse(link)
            if not url.scheme:
                link = self.record.url_to('!' + link,
                                          base_url=get_ctx().base_url)
        if '/seminarContent' in link:
            link = get_drive_url(link)
        link = escape(link)

        if not title:
            if nofollow:
                return '<a href="%s" rel="nofollow">%s</a>' % (link, text) 
            else:
                return '<a href="%s">%s</a>' % (link, text)
        title = escape(title)
        if nofollow:
            return '<a href="%s" title="%s" rel="nofollow">%s</a>' % (link, title, text)
        else:
            return '<a href="%s" title="%s">%s</a>' % (link, title, text)

class PapersTable:

    def __init__(self, table_title, table_data):
        self.table_title = table_title
        self.table_data = table_data
        self.is_organized = False

class PapersTopicData(PapersTable):

    def __init__(self, table_title, table_data):
        super().__init__(table_title, table_data)
        self.table_data = self.get_data_by_topic()
        self.is_organized = True

    def get_data_by_topic(self):
        organized_data = defaultdict(list)
        for row in self.table_data:
            category = None
            if 'theme' in row:
                category = 'theme'
            if 'track' in row:
                category = 'track'
            if category:
                organized_data[row[category]].append(row)
        return organized_data


class ConferenceTemplatePlugin(Plugin):
    name = 'FAA Human Factors Jinja Template Functions'
    description = 'Adds specific or generalized template functions to Jinja.'

    def on_markdown_config(self, config, **extra):
        config.renderer_mixins.append(LinkMixin)

    def sponsors_csv(self, year=None):
        sponsor_attachments = site_proxy.get('/sponsors/').attachments
        sponsor_data = None
        for attach in sponsor_attachments:
            if 'sponsors.csv' in attach.attachment_filename:
                sponsor_data = self._parse_csv(attach.attachment_filename)
        if sponsor_data is None:
            return []

        if year:
            return [d for d in sponsor_data if 'year' in d and d['year'].strip() == year]

        return sponsor_data

    def parse_csv(self, attachments, attachment_name):
        for attach in attachments:
            if attachment_name in attach.attachment_filename:
                return self._parse_csv(attach.attachment_filename)
        return None

    def paper_csv(self, paper_attachments, organized=False):
        relevant_attachments = []
        for attach in paper_attachments:
            if 'papers.csv' in attach.attachment_filename:
                table_data = self._parse_csv(attach.attachment_filename)
                if organized and self.has_themes(table_data):
                    pt = PapersTopicData("Accepted Papers", table_data)
                else:
                    pt = PapersTable("Accepted Papers", table_data)
                relevant_attachments.append((3,pt))
            elif 'tutorials.csv' in attach.attachment_filename:
                pt = PapersTable("Tutorials", self._parse_csv(attach.attachment_filename))
                relevant_attachments.append((2,pt))
            elif 'keynotes.csv' in attach.attachment_filename:
                pt = PapersTable("Keynotes", self._parse_csv(attach.attachment_filename))
                relevant_attachments.append((1,pt))
        # Keynotes, then tutorials, then papers
        relevant_attachments.sort()
        return [x[1] for x in relevant_attachments]
        

    def _parse_csv(self, csv_filename):
        with open(csv_filename, "r", encoding="utf8") as f:
            reader = csv.DictReader(f)
            all_items = [row for row in reader]
        if sys.version_info < (3, 0):
            return [{unicode(k, 'utf-8', errors='ignore'): unicode(v, 'utf-8', errors='ignore') for k,v in row.iteritems()} for row in all_items]
        else:
            return [{k: v for k,v in row.items()} for row in all_items]

    def has_abstracts_file(self, papers_attachment):
        return any(['abstracts_file' in row and row['abstracts_file'] for row in papers_attachment])

    def has_presentations(self, papers_attachment):
        return any(['presentation' in row and row['presentation'] for row in papers_attachment])

    def has_papers(self, papers_attachment):
        return any(['paper' in row and row['paper'] for row in papers_attachment])

    def has_videos(self, papers_attachment):
        return any(['video' in row and row['video'] for row in papers_attachment])

    def has_best(self, papers_attachment):
        return any(['best' in row and row['best'] for row in papers_attachment])

    def has_themes(self, papers_attachment):
        return any([(('track' in row and row['track']) or 
                     ('theme' in row and row['theme'])) for row in papers_attachment])

    def filter_breadcrumbs(self, pages):
        combined = []
        for page in pages:
            if 'skip_breadcrumbs' in page and page['skip_breadcrumbs']:
                break
            else:
                combined.append(page)
        return combined
    
    def page_reverse_order(self, page):
        if page is None:
            return []
        
        path = [page]
        root = page
        for i in range(1, 100):
            root = root.parent
            if root:
                path.append(root)
            else:
                break
        
        return reversed(path)

    def get_attr_funct(self, attr):
        return lambda x: getattr(x, attr)

    def make_color(self, color_num, num_colors):
        # defaults to one color - avoid divide by zero
        return color_num * (360 / num_colors) % 360;

    def get_unique_colors(self, num_colors = 20):
        if num_colors <= 1:
            num_colors = 1
        return ['hsl({}, 50%, 50%)'.format(self.make_color(i, num_colors)) for i in range(1, num_colors+1)]

    def on_setup_env(self, **extra):
        self.env.jinja_env.globals.update(paper_csv=self.paper_csv,
                                          sponsors_csv=self.sponsors_csv,
                                          has_abstracts_file=self.has_abstracts_file,
                                          has_presentations=self.has_presentations,
                                          has_papers=self.has_papers,
                                          has_videos=self.has_videos,
                                          has_best=self.has_best,
                                          has_themes=self.has_themes,
                                          get_drive_url=get_drive_url,
                                          unicode=unicode,
                                          get_unique_colors=self.get_unique_colors,
                                          page_reverse_order=self.page_reverse_order,
                                          filter_breadcrumbs=self.filter_breadcrumbs,
                                          parse_csv=self.parse_csv,
                                          enumerate=enumerate,
                                          set=set,
                                          list=list,
                                          reversed=reversed,
                                          get_attr_funct=self.get_attr_funct,
                                          len=len,
                                          dir=dir,
                                          sorted=sorted)
        self.env.jinja_env.filters['drive'] = get_drive_url
        self.env.jinja_env.add_extension('jinja2.ext.loopcontrols')
