"""
EZID plugin views module (currently placeholder)
"""
from django.shortcuts import render


def ezid_manager(request):
    template = 'ezid/manager.html'
    context = {}
    return render(request, template, context)
