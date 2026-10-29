"""Atomic, source-shared HTTP intent budgets. Denials never spend task attempts."""
class RequestDeferred(RuntimeError):
 def __init__(self,seconds):self.seconds=max(0,float(seconds));super().__init__('SOURCE_REQUEST_BUDGET_DEFERRED')

class SourcePaused(RuntimeError):pass

def reserve(coordinator,ticket,cost=1,limit=30,window=60,spacing=2):
 if type(cost) is not int or not 0<=cost<=limit or type(limit) is not int or limit<1 or window<=0 or spacing<0:raise ValueError('RATE_POLICY')
 now=coordinator.clock()
 def change(state):
  task=coordinator.owned(state,ticket)
  if task['status']!='LEASED':raise ValueError('RATE_RESERVATION_REQUIRES_LEASE')
  if state.get('hold'):return max(60,state.get('cooldown_until',0)-now)
  if state.get('cooldown_until',0)>now:return state['cooldown_until']-now
  rate=state.setdefault('http_budget',dict(intents=[],next_at=0,policy=dict(limit=limit,window=window,spacing=spacing)))
  if rate['policy']!=dict(limit=limit,window=window,spacing=spacing):raise ValueError('SHARED_RATE_POLICY_CHANGED')
  intents=[x for x in rate['intents'] if x['at']>now-window]
  delay=max(0,rate['next_at']-now)
  if sum(x['cost'] for x in intents)+cost>limit:delay=max(delay,min(x['at'] for x in intents)+window-now)
  rate['intents']=intents
  if delay:return delay
  if cost:intents.append(dict(at=now,cost=cost,key=ticket['key'],fence=ticket['fence']))
  rate['next_at']=now+spacing*cost
  return 0
 delay=coordinator.update(change)
 if delay:raise RequestDeferred(delay)
