from optparse import make_option
from dealfu.esutils import EsDealsQuery

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import xlsxwriter



class Command(BaseCommand):
    """
    Es Dump Management
    """

    option_list = BaseCommand.option_list + (
        make_option('--output-format',
                    action='store',
                    help='output format to put data in',
                    dest="output_format",
                    default="xlsx"),
        make_option('--output-file',
                    action='store',
                    help='file path to store data in',
                    dest="output_file",
                    default="out.xlsx"),
    )

    help = "Es dumping tasks"

    def handle(self, *args, **options):
        """
        handle params
        """
        output_format = options["output_format"]
        output_file = options["output_file"]
        query = EsDealsQuery()

        #self.stdout.write(output_format)
        #self.stdout.write(output_file)


        if output_format == "xlsx":
            self._es_dump_xlsx(query, output_file)
        else:
            raise CommandError("Not supported output format [xlsx]")


    def _iter_query(self, query):

        total = 1
        page = 0
        page_size = 100


        while total != 0:
            query = query.filter_page(page=page, per_page=page_size)
            page += page_size
            print page
            fetch = query.query
            total = len(fetch)
            query.reset()
            print total
            yield fetch



    def _es_dump_xlsx(self, query, outfile):
        """
        Gets a EsDealsQuery and dumps to a xlsx file
        """
        workbook = xlsxwriter.Workbook(outfile,{'constant_memory': True})
        worksheet = workbook.add_worksheet("coupons")


        #self.stdout.write(str(res))
        #now lets store some data into xlsx
        column_names = [
            "category_name",
            "category_id",
            "parent_cat_name",
            "parent_cat_id",
            "coupon_pk",
            "sqoot_ref_id",
            "ref_id_source",
            "online",
            "merchant_pk",
            "dealtypes",
            "description",
            "restrictions",
            "code",
            "start",
            "end",
            "link",
            "directlink",
            "skimlinks",
            "status",
            "lastupdated",
            "created",
            "countries",
            "coupon_network",
            "price",
            "listprice",
            "discount",
            "percent",
            "image",
            "short_desc",
            "desc_slug",
            "is_featured",
            "is_new",
            "is_popular",
            "is_duplicate",
            "is_active",
            "is_deleted",
            "related_deal",
            "popularity",
            "coupon_type",
            "embedly_title",
            "embedly_description",
            "embedly_image_url",
            "ml_pk",
            "ml_address",
            "ml_locality",
            "ml_region",
            "ml_zip",
            "ml_lng",
            "ml_lat"
        ]

        for i, c in enumerate(column_names):
            worksheet.write(0, i, c)


        for page, q in enumerate(self._iter_query(query)):
            for row, item in enumerate(q):
                xls_item = self._convert_dbitem_to_xlsitem(item["_source"], item["_id"], column_names)
                for c, x in enumerate(xls_item):
                    worksheet.write((page*100)+row+1, c, x)

        workbook.close()


    def _apply_dict_to_xls_item(self, d, colnames, item):
        for c, cname in enumerate(colnames):
            if d.has_key(cname):
                item[c] = d.get(cname)

        return item

    def _get_default_xls_item(self, colnames):
        xls_item = ["n/a" for c in colnames]

        default_dict = {
            "dealtypes":"Online",
            "status":"unconfirmed",
            "countries":"usa",
            "is_featured":"FALSE",
            "is_new":"FALSE",
            "is_popular":"FALSE",
            "is_duplicate":"FALSE",
            "is_active":"FALSE",
            "is_deleted":"FALSE",
            "popularity":"0",
            "ml_lng":"0",
            "ml_lat":"0"
        }


        return self._apply_dict_to_xls_item(default_dict, colnames, xls_item)



    def _convert_dbitem_to_xlsitem(self, dbitem, dbid, colnames):
        fresh_xls_item = self._get_default_xls_item(colnames)
        #print fresh_xls_item
        xls_item = {}

        xls_item["category_name"] = dbitem.get("category_name", "general")
        xls_item["coupon_pk"] = dbid
        xls_item["ref_id_source"] = dbitem.get("provider_slug", "groupon")
        xls_item["online"] = dbitem.get("online", "n/a")
        xls_item["description"] = dbitem.get("description", "n/a")
        xls_item["end"] = dbitem.get("expires_at", "n/a")
        xls_item["link"] = "/api/deals/"+dbid+"/?api_key=%s"%settings.AUTH_KEY
        xls_item["directlink"] = dbitem.get("untracked_url", "n/a")
        xls_item["created"] = dbitem.get("expires_at", "n/a")
        xls_item["coupon_network"] = dbitem.get("provider_name", "n/a")
        xls_item["price"] = dbitem.get("price", "n/a")
        xls_item["listprice"] = dbitem.get("value", "n/a")
        xls_item["discount"] = dbitem.get("discount_amount", "n/a")
        xls_item["percent"] = dbitem.get("discount_percentage", 0) * 100
        xls_item["image"] = dbitem.get("image_url", "n/a")
        xls_item["short_desc"] = dbitem.get("short_title", "n/a")
        xls_item["embedly_title"] = dbitem.get("title", "n/a")
        xls_item["embedly_description"] = dbitem.get("short_title", "n/a")
        xls_item["embedly_image_url"] = dbitem.get("image_url", "n/a")

        merchant = dbitem.get("merchant")
        if merchant:
            addresses = dbitem["merchant"]["addresses"]
        else:
            addresses = []


        if merchant and addresses:
            xls_item["ml_address"] = addresses[0].get("address", "n/a")
        else:
            xls_item["ml_address"] = "n/a"
        if merchant and addresses:
            xls_item["ml_locality"] = addresses[0].get("address_name", "n/a")
        else:
            xls_item["ml_locality"] = "n/a"
        if merchant and addresses:
            xls_item["ml_region"] = addresses[0].get("region", "n/a")
        else:
            xls_item["ml_region"] = "n/a"
        if merchant and addresses:
            xls_item["ml_zip"] = addresses[0].get("postal_code", "n/a")
        else:
            xls_item["ml_zip"] = "n/a"

        return self._apply_dict_to_xls_item(xls_item, colnames, fresh_xls_item)
