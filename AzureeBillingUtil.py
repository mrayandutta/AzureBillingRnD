import os,json,requests,urllib,pprint,datetime,logging
import ConfigParser
from collections import Counter

iniFile = ConfigParser.SafeConfigParser()
iniFile.read(os.path.abspath(os.path.dirname(__file__)) + '/credentials.properties')

LOG_FILE_NAME= "azure_billing.log"

#Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# create a file handler
fh = logging.FileHandler(LOG_FILE_NAME)
fh.setLevel(logging.INFO)

# create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)

ch = logging.StreamHandler()
ch.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)


#Azure Related Information
apiVer          = iniFile.get('Azure', 'AZURE_API_VER')
tenantID        = iniFile.get('Azure', 'AZURE_TENANT_ID')
clientID        = iniFile.get('Azure', 'AZURE_CLIENT_ID')
clientPW        = iniFile.get('Azure', 'AZURE_CLIENT_SECRET')
subscriptionsID = iniFile.get('Azure', 'AZURE_SUBSCRIPTION_ID')


offerDurableID  = 'MS-AZR-0044P'
defCurrency     = 'INR'
defLocale       = 'en-US'
defRegion       = 'IN'



logger.info("API Version:::" + str(apiVer))


# AzureAPI AuthToken
def GetAuthToken():
    url = "https://login.microsoftonline.com/" + tenantID + "/oauth2/token?api-version=1.0"
    header = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {'client_id': clientID,
            'client_secret': clientPW,
            'grant_type': 'client_credentials',
            'resource': 'https://management.azure.com/'}

    # AuthToken
    resp = requests.post(
        url,
        headers=header,
        data=data)

    defToken = resp.json().get('access_token')
    return defToken


# Get Azure Resource Usage data using the REST API
def GetAzureResourceUsage(defSubscriptionsID, defAuthToken, defStartDay, defEndDay):
    url = "https://management.azure.com/subscriptions/" + defSubscriptionsID + "/providers/Microsoft.Commerce/UsageAggregates" + \
          "?api-version=" + apiVer + \
          "&reportedStartTime=" + defStartDay + \
          "&reportedEndTime=" + defEndDay + \
          "&showDetails=false"
    header = {'Authorization': 'Bearer ' + defAuthToken, 'Content-Type': 'application/json'}

    #
    resp = requests.get(
        url,
        headers=header)

    #
    jsonData = resp.json().get('value')

    # Azure RestAPI
    while resp.json().get('nextLink') != None:
        # URL
        url = resp.json().get('nextLink')

        #
        resp = requests.get(
            url,
            headers=header)

        # JSON_DATA
        jsonData += resp.json().get('value')

    # ('properties')

    data = []
    for attr in jsonData:
        data.append(attr.get('properties'))

    # DATA
    return data
#Get the Total by MeterID of Azure usage data (quantity)
def GetQuantitySum(inData):
    counterData = Counter()
    for val in inData:
        counterData[val['meterId']] += val['quantity']
    dictData = dict()
    for k,v in dict(counterData).items():
        dictData[k] = dict({"quantity": v})
    return dictData


def GetAzureRateCard(defSubscriptionsID, defAuthToken, defOfferDurableID):

    '''
    defCurrency = 'EUR'
    defLocale = 'en-US'
    defRegion = 'US'
    '''

    searchQuery = "OfferDurableId eq '" + defOfferDurableID + "'" + \
                  " and Currency eq '" + defCurrency + "'" + \
                  " and Locale eq '" + defLocale + "'" + \
                  " and RegionInfo eq '" + defRegion + "'"

    url = "https://management.azure.com/subscriptions/" + defSubscriptionsID + "/providers/Microsoft.Commerce/RateCard" + \
          "?api-version=" + apiVer + "&$filter=" + urllib.quote(searchQuery)
    header = {'Authorization': 'Bearer ' + defAuthToken, 'Content-Type': 'application/json'}

    resp = requests.get(
        url,
        headers=header)
    data = resp.json().get('Meters')
    return data

def GetRateData(inData):
    dictData = dict()
    for k in inData:
        dictData[k["MeterId"]] = dict({"MeterRates": k["MeterRates"]['0'],
                                        "MeterName": k["MeterName"],
                                        "MeterCategory": k["MeterCategory"],
                                        "MeterSubCategory": k["MeterSubCategory"],
                                        "Unit": k["Unit"],
                                       })
    return dictData


# Rate
def JoinQuantityAndRate(usageDictData,rateDictData):
    logger.info("------------------------------ JoinQuantityAndRate Details:---------------------------------------")
    dictData = dict()
    for k in usageDictData:
        if( (usageDictData[k]["quantity"]>0) and (rateDictData[k]["MeterRates"])):
            #logger.info("quantity:" + str(usageDictData[k]["quantity"])+",MeterRates:" + str(rateDictData[k]["MeterRates"])+"Fee :" + str(usageDictData[k]["quantity"] * rateDictData[k]["MeterRates"]))
            logger.info("MeterCategory:'" + str(rateDictData[k][
                "MeterCategory"])  +"',Quantity:" + str(usageDictData[k]["quantity"]) + ",MeterRates:" + str(
                rateDictData[k]["MeterRates"]) + ",Fee :" + str(
                usageDictData[k]["quantity"] * rateDictData[k]["MeterRates"])+",Unit:" + str(rateDictData[k]["Unit"]))
            #logger.info("Unit:" + str(rateDictData[k]["Unit"]))
        dictData[k] = dict({"quantity": usageDictData[k]["quantity"],
                            "MeterRates": rateDictData[k]["MeterRates"],
                            "MeterName": rateDictData[k]["MeterName"],
                            "MeterFee": usageDictData[k]["quantity"] * rateDictData[k]["MeterRates"],
                            "MeterCategory": rateDictData[k]["MeterCategory"],
                            "MeterSubCategory": rateDictData[k]["MeterSubCategory"]})
    return dictData

def SumUsagefeeByCategory(inData):
    counterData = Counter()
    for k in inData:
        counterData[inData[k]['MeterCategory']] += inData[k]['MeterFee']
    dictData = dict()
    for k,v in dict(counterData).items():
        dictData[k] = int(v)
    return dictData

def SumUsagefee(inData):
    counterData = Counter()
    for k in inData:
        counterData['ALL'] += inData[k]['MeterFee']
    return int(counterData['ALL'])

# GET TOKEN
token = GetAuthToken()
logger.info("token:" + str(token))

#Get yesterday Date
#dateTimePattern ="%Y-%m-%dT%H:%M:%S"
dateTimePattern ="%Y-%m-%d"
lastDay = datetime.date.today()
#lastDayStr = lastDay.strftime('%Y-%m-%d')
lastDayStr = lastDay.strftime(dateTimePattern)

#Let the start date be the last day of last month
#lastMonth   = lastDay - datetime.timedelta(days=lastDay.day)
lastMonth   = lastDay - datetime.timedelta(days=90)
startDayStr = lastMonth.strftime(dateTimePattern)

#startDayStr="2017-08-01T00:00:00+00:00"
#lastDayStr="2017-09-01T00:00:00+00:00"


logger.info(" startDayStr:" + str(startDayStr)+",lastDayStr:"+str(lastDayStr))
usageJson = GetAzureResourceUsage(subscriptionsID,token,startDayStr,lastDayStr)
logger.info("usageJson:" + str(usageJson))
usageDict = GetQuantitySum(usageJson)
#logger.info("usageDict:" + str(usageDict))

reteJson = GetAzureRateCard(subscriptionsID,token,offerDurableID)
#logger.info("reteJson:" + str(reteJson))
rateDict = GetRateData(reteJson)
#logger.info("rateDict:" + str(rateDict))

#print "rateDict:",rateDict

usageData = JoinQuantityAndRate(usageDict,rateDict)
#logger.info("usageData:" + str(usageData))
categorySum = SumUsagefeeByCategory(usageData)
logger.info("categorySum:" + str(categorySum))
totalSum = SumUsagefee(usageData)
logger.info("totalSum:" + str(totalSum))


attachments=[]
attachment={'pretext': 'Test','fields': []}
for k in categorySum:
    item={'title': k ,'value': 'Rs/ ' + "{:,d}".format(categorySum[k]) ,'short': "true"}
    attachment['fields'].append(item)

logger.info("attachment:" + str(attachment))