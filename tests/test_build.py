import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('irc_build', Path(__file__).resolve().parents[1] / 'scripts/build.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class BuildTests(unittest.TestCase):
    def write_csv(self, root, day, rows):
        file = root / f'lost/{day[:4]}/{day[5:7]}/{day}.csv'
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow(module.HEADER)
            writer.writerows(rows)
        return file

    def test_csv_quotes_multiline_unicode_and_timestamp_ties_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [('2010-01-01 12:00:00', 'älice', 'a,"quoted"\nsecond line'),
                    ('2010-01-01 12:00:00', 'bob', '<script>alert(1)</script>')]
            file = self.write_csv(root, '2010-01-01', rows)
            self.assertEqual(module.read_day(file, '2010-01-01'), rows)
            module.build(root, root.parent / (root.name + '-site'), root.parent / (root.name + '-work'), 2, 1)
            import shutil
            site, work = root.parent / (root.name + '-site'), root.parent / (root.name + '-work')
            try:
                html = (site / module.page_name('lost', '2010-01-01')).read_text()
                self.assertIn('a,&quot;quoted&quot;\nsecond line', html)
                self.assertIn('&lt;script&gt;', html)
                self.assertNotIn('<script>alert', html)
                self.assertEqual((site / 'csv/lost/2010/01/2010-01-01.csv').read_bytes(), file.read_bytes())
                records = [json.loads(line) for line in (work / 'search-records.jsonl').read_text().splitlines()]
                self.assertIn('a,"quoted"\nsecond line', records[0]['content'])
                self.assertTrue(records[1]['url'].endswith('#m000002'))
            finally:
                shutil.rmtree(site)
                shutil.rmtree(work)

    def test_pagination_and_day_navigation_preserve_all_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [(f'2010-01-01 12:00:0{i}', 'nick', str(i)) for i in range(5)]
            self.write_csv(root / 'logs', '2010-01-01', rows)
            self.write_csv(root / 'logs', '2010-01-03', [('2010-01-03 00:00:00', 'n', 'last')])
            result = module.build(root / 'logs', root / 'site', root / 'build', 2, 1)
            self.assertEqual(result['messages'], 6)
            self.assertEqual(result['log_pages'], 4)
            self.assertEqual(result['search_records'], 6)
            html = (root / 'site' / module.page_name('lost', '2010-01-01', 2)).read_text()
            self.assertIn('id="m000005"', html)
            self.assertIn('page-002.html', html)
            self.assertIn('../2010-01-03/index.html', html)
            self.assertNotIn('2010-01-02/index.html', html)

    def test_invalid_dates_order_headers_and_columns_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rows in [[('2010-01-02 00:00:00', 'n', 'wrong day')],
                         [('2010-01-01 12:00:00', 'n', 'later'), ('2010-01-01 11:00:00', 'n', 'earlier')],
                         [('2010-01-01 00:00:00', 'extra', 'columns', 'bad')]]:
                file = self.write_csv(root, '2010-01-01', rows)
                with self.assertRaises(ValueError):
                    module.read_day(file, '2010-01-01')
            file.write_text('nick,message\nn,hello\n')
            with self.assertRaises(ValueError):
                module.read_day(file, '2010-01-01')

    def test_links_escape_html_without_creating_script_urls(self):
        html = module.linkify('<img src=x> https://example.org/?a=1&b=2 javascript:alert(1) http://[broken')
        self.assertIn('&lt;img', html)
        self.assertIn('href="https://example.org/?a=1&amp;b=2"', html)
        self.assertNotIn('href="javascript:', html)
        self.assertNotIn('href="http://[broken', html)
        self.assertIn('http://[broken', html)
        self.assertEqual(module.href('search/index.html', 'static/search.js'), '../static/search.js')


if __name__ == '__main__':
    unittest.main()
