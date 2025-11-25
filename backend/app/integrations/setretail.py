from zeep import Client

WSDL_URL = "http://192.168.50.90:8090/SET-ERPIntegration/FiscalInfoExport?wsdl"

client = Client(WSDL_URL)

def get_new_purchases():
    response = client.service.getNewPurchasesByOperDay()
    return response
