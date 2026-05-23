from django.contrib import admin
from .models import Review, Feedback, SearchLog, ExternalSource, DataSyncHistory

admin.site.register(Review)
admin.site.register(Feedback)
admin.site.register(SearchLog)
admin.site.register(ExternalSource)
admin.site.register(DataSyncHistory)