"""Independent, limited RV32 instruction runner for P1 artifact checks.
Not XSim, not cycle accurate, not a general RISC-V implementation.
Unsupported instructions and out-of-range accesses fail closed.
"""
MASK=0xffffffff
def sx(x,b):return x-(1<<b) if x&(1<<(b-1)) else x

def execute(imem,initial,base=0x80000000,limit=1000000,trace=None):
    pc=base; dbase=0x20000000 if base else 0
    regs=[0]*32; mem=initial.copy(); csr={}; done=0x444f4e45
    def index(addr):
        if addr%4 or not dbase<=addr<dbase+65536:raise ValueError(f'Bad DMEM address {addr:x}')
        return (addr-dbase)//4
    for steps in range(1,limit+1):
        if pc%4 or not base<=pc<base+65536:raise ValueError('Bad instruction PC')
        ins=imem[(pc-base)//4];op=ins&127;rd=(ins>>7)&31;f3=(ins>>12)&7
        rs1=(ins>>15)&31;rs2=(ins>>20)&31;f7=ins>>25
        a,b=regs[rs1],regs[rs2];nextpc=(pc+4)&MASK;value=None
        if op==0x17:value=pc+(ins&0xfffff000)
        elif op==0x37:value=ins&0xfffff000
        elif op==0x13:
            imm=sx(ins>>20,12)
            if f3==0:value=a+imm
            elif f3==1 and f7==0:value=a<<(rs2&31)
            elif f3==5 and f7==0:value=a>>(rs2&31)
            else:raise ValueError('Unsupported OP-IMM')
        elif op==0x33:
            if f3==0 and f7==0:value=a+b
            elif f3==0 and f7==0x20:value=a-b
            elif f3==0 and f7==1:value=a*b
            elif f3==6 and f7==0:value=a|b
            else:raise ValueError('Unsupported OP')
        elif op==3 and f3==2:value=mem[index((a+sx(ins>>20,12))&MASK)]
        elif op==0x23 and f3==2:
            imm=sx(((ins>>25)<<5)|((ins>>7)&31),12)
            addr=(a+imm)&MASK;mem[index(addr)]=b
            if addr==dbase+20 and b==done:return mem,regs,csr,steps
        elif op==0x63:
            imm=((ins>>31)<<12)|(((ins>>7)&1)<<11)|(((ins>>25)&63)<<5)|(((ins>>8)&15)<<1)
            cond={0:a==b,1:a!=b,4:sx(a,32)<sx(b,32),5:sx(a,32)>=sx(b,32),6:a<b,7:a>=b}
            if f3 not in cond:raise ValueError('Unsupported branch')
            if cond[f3]:nextpc=(pc+sx(imm,13))&MASK
        elif op==0x6f:
            imm=((ins>>31)<<20)|(((ins>>12)&255)<<12)|(((ins>>20)&1)<<11)|(((ins>>21)&1023)<<1)
            value=pc+4;nextpc=(pc+sx(imm,21))&MASK
        elif op==0x73 and f3==1:
            address=ins>>20
            if address not in (0x304,0x305):raise ValueError('Unsupported CSR')
            value=csr.get(address,0);csr[address]=a
        elif op==0x0f and f3==0:pass
        else:raise ValueError(f'Unsupported instruction {ins:08x} at {pc:08x}')
        if trace is not None:trace.append({'pc':pc,'instruction':ins,'branch':op==0x63,'taken':op==0x63 and cond[f3]})
        if value is not None and rd:regs[rd]=value&MASK
        regs[0]=0;pc=nextpc
    raise ValueError('Instruction budget exhausted without done')
