import unicodecsv as csv

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpResponseRedirect, HttpResponse
from django.views.generic import DetailView, ListView
from django.views.generic.edit import FormView, UpdateView
from django.shortcuts import render
from django.urls import reverse
from django.utils.safestring import mark_safe

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.fields import CurrentUserDefault
from rest_framework.views import APIView
from rest_framework.response import Response

from dal import autocomplete

from django_tables2 import SingleTableMixin, SingleTableView

from mailer_server.mail import jobs
from mailer_server.mail.serializers import MailSerializer, MassMailSerializer

from mailer_server.mail import models, forms, tables, filters

from mailer_server.core.mixins import FilterOwnerMixin
from mailer_server.mail.mixins import FilteredSingleTableMixin

class UserPermissionRequiredMixin(PermissionRequiredMixin, ):
    permission_required = 'core.user'


@permission_required('core.admin')
def send_test_email(request):
    msg = mark_safe('Sending test email ...')
    messages.info(request, msg)
    jobs.send_test_mail(request.user)
    return HttpResponseRedirect(reverse('home'))


class SendMailAPIView(APIView):
    #authentication_classes = (TokenAuthentication, )

    def get(self, request, format=None):
        serializer = MailSerializer(data=request.data)
        return Response(serializer.data)

    def post(self, request, format=None):
        print request.data

        serializer = MailSerializer(data=request.data, )
        if serializer.is_valid():

            mail = serializer.save(created_by=self.request.user)
            jobs.send_mail(mail)
            return Response(status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendMassMailAPIView(APIView):

    def get(self, request, format=None):
        serializer = MassMailSerializer(data=request.data)
        return Response(serializer.data)

    def post(self, request, format=None):

        mm_serializer = MassMailSerializer(data=request.data, )

        if mm_serializer.is_valid():

            if jobs.send_mass_mail(mm_serializer, self.request.user):
                return Response( status=status.HTTP_200_OK)
            else:
                print "Cannot send mails - service not available!"
                return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(mm_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendMassMailFormView(UserPermissionRequiredMixin, FormView):
    form_class = forms.SendMailForm
    template_name = 'send_mail.html'

    def form_valid(self, form):
        # Stupid DRF! I have to use a serializer here that is filled from the form to keep a common API
        # with the jobs. Notice that I don't care about the validity of the serializer since it shoud
        # have been validated from the form -- I just use is_valid to allow saving in the job

        mm_serializer  = MassMailSerializer(data={
            'mail_template': form.cleaned_data['mail_template'].id,
            'distribution_list_to': form.cleaned_data['distribution_list'].id,
        })
        mm_serializer.is_valid()
        if jobs.send_mass_mail(mm_serializer, self.request.user):

            messages.info(self.request, 'Started sending emails!')
        else:
            messages.info(self.request, 'Not able to send any emails!')

        return HttpResponseRedirect(reverse('home'))


class DistributionListAutocomplete(UserPermissionRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated():
            return DistributionList.objects.none()

        qs = models.DistributionList.objects.filter(created_by=self.request.user)

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs


class MailTemplateAutocomplete(UserPermissionRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated():
            return MailTemplate.objects.none()

        qs = models.MailTemplate.objects.filter(created_by=self.request.user)

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs


class UploadDistributionListView(UserPermissionRequiredMixin, FilterOwnerMixin, UpdateView):
    model = models.DistributionList
    form_class = forms.UploadDistributionListForm
    template_name = 'upload_dl.html'

    def form_valid(self, form):
        self.object.emailaddress_set.all().delete()
        models.EmailAddress.objects.bulk_create(form.emails)
        messages.info(self.request, "Updated emails for distribution list!")
        return HttpResponseRedirect(self.object.get_absolute_url())


class DownloadDistributionListView(DetailView):
    model = models.DistributionList

    def render_to_response(self, context, **response_kwargs):
        response = HttpResponse(content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename=export.csv'

        w = csv.writer(response, encoding='utf-8', delimiter=',', quotechar='"')
        w.writerow(('name', 'email', ))
        for email in self.object.emailaddress_set.all().order_by('name', 'email', ):
            w.writerow((email.name, email.email))

        return response


class MailListView(FilterOwnerMixin, FilteredSingleTableMixin, ListView):
    model = models.Mail
    table_class = tables.MailTable
    filter_class = filters.MailFilter


class MassMailListView(FilterOwnerMixin, FilteredSingleTableMixin, ListView):
    model = models.MassMail
    table_class = tables.MassMailTable
    filter_class = filters.MassMailFilter
