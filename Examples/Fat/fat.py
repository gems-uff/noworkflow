
def fat(n):
  if n == 0 or n == 1:
    return 1
  return n * fat(n-1)
#  for i in range (1,n):
#    resp += i *1
#  saida = open("saida.txt","wt"):
#  saida.write(resp)
#  saida.close
#  return resp

fat(5)
