from optparse import make_option
import os
import json

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from elasticsearch.client import IndicesClient

from dealfu.esutils import EsHandleMixin

class EsHandler(EsHandleMixin):
    pass

es = EsHandler()


class Command(BaseCommand):
    """
    Es management tasks
    """

    option_list = BaseCommand.option_list + (
        make_option('--cmd',
                    action='store',
                    help='name of the action [init, reset]',
                    dest="cmd"),

        make_option("--mapping",
                    action="store",
                    help="the path of the mapping",
                    dest="mapping"),
    )

    help = "Some es index management tasks"

    def handle(self, *args, **options):
        if not options["cmd"]:
            raise CommandError("cmd parameter is mandatory")

        if options["cmd"] == "init":
            self._init_mapping(options["mapping"])
        elif options["cmd"] == "reset":
            self._reset_mapping(options["mapping"])
        else:
            raise CommandError("invalid cmd parameter")

        self.stdout.write("Success!")

    def _init_mapping(self, mapping_path):
        esi = IndicesClient(es.get_es_handle())
        index = settings.ES_INDEX

        #first create index if not exists
        if not esi.exists(index):
            self.stdout.write("Creating index for db : %s"%index)
            esi.create(index=index)
            self.stdout.write("Index Created for : %s"%index)


        if not mapping_path or not os.path.exists(mapping_path):
            raise CommandError("not existing mapping path")

        mapping_str = open(mapping_path, "r").read()
        mappings = json.loads(mapping_str)


        for k,v in mappings.iteritems():
            res = esi.put_mapping(index, k, {k:mappings[k]})
            self.stdout.write(str(res))



    def _reset_mapping(self, mapping_path):
        esi = IndicesClient(es.get_es_handle())
        index = settings.ES_INDEX

        if not esi.exists(index):
            raise CommandError("Non existing index : %s"%index)

        self.stdout.write(esi.delete(index=index))

