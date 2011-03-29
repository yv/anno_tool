import heapq

def dijkstra_search(sources,goals,expand,limit=None):
    ns_closed={}
    ns_open=[]
    for source in sources:
        ns_open.append((0,source,None,None))
    while ns_open:
        oldcost,node,direction,prevnode=heapq.heappop(ns_open)
        if limit and oldcost>limit:
            return None
        if node not in ns_closed:
            #print "popped %s(%s)"%(node,oldcost)
            ns_closed[node]=(direction,prevnode)
            if node in goals:
                path=[]
                n=prevnode
                n_old=node
                dir=direction
                while n is not None:
                    path.append(dir)
                    n_old=n
                    dir,n=ns_closed[n]
                return (oldcost,n_old,node,path)
            for arc_cost,newnode,direction in expand(node):
                heapq.heappush(ns_open,(oldcost+arc_cost,newnode,direction,node))
    # search terminated without a path

def test_search():
    graph={1:[2,3],
            2:[1,3,5],
            3:[1,2,4],
            4:[3,5,6],
            5:[2,4,6],
            6:[4,5]}
    return dijkstra_search([1],[6],lambda x: [(1,y,x) for y in graph[x]])
