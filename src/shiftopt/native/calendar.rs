// Intersect precomputed windows for arbitrary cumulative resources and consumable stocks.
use std::slice;

#[no_mangle]
pub unsafe extern "C" fn filter_calendar(
    resources:usize,t:usize,templates:usize,n:usize,nw:usize,ns:usize,nfixed:usize,include:usize,
    cap:*const i32,win:*const i32,sp:*const i64,seg:*const i32,cp:*const i64,ci:*const i32,
    quantity:*const f64,stock:*const f64,ap:*const i64,types:*const i32,starts:*const i32,
    fixed:*const i64,result:*mut i32,
)->i64 {
    if t==0 || n>i32::MAX as usize {return -1;}
    let cap=slice::from_raw_parts(cap,resources*t);
    let win=slice::from_raw_parts(win,nw*3);
    let sp=slice::from_raw_parts(sp,templates+1);
    let seg=slice::from_raw_parts(seg,sp[templates] as usize*2);
    let cp=slice::from_raw_parts(cp,templates+1);
    let ci=slice::from_raw_parts(ci,cp[templates] as usize);
    let q=slice::from_raw_parts(quantity,ci.len());
    let mut stock=slice::from_raw_parts(stock,ns).to_vec();
    let ap=slice::from_raw_parts(ap,templates+1);
    let types=slice::from_raw_parts(types,n);
    let starts=slice::from_raw_parts(starts,n);
    let fixed=slice::from_raw_parts(fixed,nfixed);
    let out=slice::from_raw_parts_mut(result,n);
    let mut residual=cap.to_vec();
    let mut marked=vec![false;n];
    for &j in fixed {
        let j=j as usize;
        marked[j]=true;
        let a=types[j] as usize;
        for z in sp[a] as usize..sp[a+1] as usize {
            let w=seg[2*z] as usize*3;
            let pos=win[w] as usize*t+starts[j] as usize+seg[2*z+1] as usize;
            for v in &mut residual[pos..pos+win[w+1] as usize] {
                if *v<win[w+2] {return -1;}
                *v-=win[w+2];
            }
        }
        for z in cp[a] as usize..cp[a+1] as usize {
            let i=ci[z] as usize;
            stock[i]-=q[z];
            if stock[i] < -1e-9 {return -1;}
        }
    }
    let words=1+(t-1)/128;
    let mut available=vec![0u128;nw*words];
    for (id,w) in win.chunks_exact(3).enumerate() {
        let base=w[0] as usize*t;
        let mut run=0;
        for tick in (0..t).rev() {
            run=if residual[base+tick]>=w[2] {run+1} else {0};
            if run>=w[1] {
                available[id*words+tick/128]|=1u128<<(tick%128);
            }
        }
    }
    let mut count=0;
    let mut valid=vec![0u128;words];
    for a in 0..templates {
        let supplied=(cp[a] as usize..cp[a+1] as usize)
            .all(|z| q[z]<=stock[ci[z] as usize]+1e-9);
        valid.fill(if supplied {u128::MAX} else {0});
        for z in sp[a] as usize..sp[a+1] as usize {
            let window=seg[2*z] as usize;
            let offset=seg[2*z+1] as usize;
            let shift=offset%128;
            for (word,bits) in valid.iter_mut().enumerate() {
                let pos=word+offset/128;
                let mut mask=if pos<words {available[window*words+pos]>>shift} else {0};
                if shift!=0 && pos+1<words {
                    mask|=available[window*words+pos+1]<<(128-shift);
                }
                *bits &= mask;
            }
        }
        for j in ap[a] as usize..ap[a+1] as usize {
            let tick=starts[j] as usize;
            let eligible=if marked[j] {include!=0} else {(valid[tick/128]>>(tick%128)) & 1 != 0};
            if eligible {out[count]=j as i32; count+=1;}
        }
    }
    count as i64
}
