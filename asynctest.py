from requests_futures.sessions import FuturesSession
from concurrent.futures import as_completed

import time

def bg_callback(session, response):
    response.data = response.json()

url = 'https://esi.tech.ccp.is/latest/markets/10000002/orders/'
npages = 30
paramslist = [{'page': ii} for ii in range(1,npages+1)]

t1 = time.time()

concurrent = npages
with FuturesSession(max_workers=concurrent) as sesh:
    futures = {}
    for params in paramslist:
        future = sesh.get(url, params=params, background_callback=bg_callback)
        futures[future] =  params['page']

    orders = []
    print('Got pages: ', end='')
    for future in as_completed(futures):
        print('{},'.format(futures[future]), end='')
        orders.extend(future.result().data)

t2 = time.time() - t1
print('')

print('Total time: {} sec ({} per page)'.format(t2, t2/npages))
