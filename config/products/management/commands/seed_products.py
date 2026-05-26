from django.core.management.base import BaseCommand
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../..'))


class Command(BaseCommand):
    help = '네이버 쇼핑 API로 화장품 제품 데이터 적재'

    def add_arguments(self, parser):
        parser.add_argument('--sync', action='store_true', help='주간 동기화 모드')
        parser.add_argument('--keywords', nargs='+', help='키워드 직접 지정')

    def handle(self, *args, **options):
        from scripts.seed_products import run, COSMETICS_KEYWORDS
        keywords = options['keywords'] or COSMETICS_KEYWORDS
        run(keywords, sync_mode=options['sync'])
        self.stdout.write(self.style.SUCCESS('완료'))
