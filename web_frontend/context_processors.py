from web_frontend import settings, version

def folder_urls(request):
    return {
        'static_url': settings.MEDIA_URL.lstrip('/').rstrip('/'),
        'subfolder': settings.SITE_SUBFOLDER.lstrip('/').rstrip('/'),
        'host' : request.get_host(),
    }
    
def cc_version(request):
    return {
        'version' : version.version,
    }
