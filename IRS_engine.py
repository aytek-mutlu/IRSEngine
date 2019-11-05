# -*- coding: utf-8 -*-
"""
Created on Mon Nov  4 11:23:25 2019

@author: aytekm
"""

import pandas as pd
import numpy as np
import datetime as dt
import copy
from dateutil.relativedelta import relativedelta
import scipy.optimize as opt


class Curve:
    
    def __init__(self, curve_df,compound_freq):
        self.curve_df = curve_df
        self.max_dtm = curve_df.Dtm.max()
        self.compound_freq = compound_freq
        
        def Interpolate3M(df):
            for d in np.arange(90,self.max_dtm,90):
                df.loc[d] = np.interp(d,df.index,list(df))
                df.sort_index(inplace=True)
            return df
            
            
        def ZeroCurve(df):
            zero_df = pd.Series(index = df.index,name='Rate')
            zero_df.loc[:compound_freq] = df.loc[:compound_freq]
            self.discount_factor.loc[:compound_freq] = 1/pow((1+zero_df.loc[:compound_freq]/100),zero_df.loc[:compound_freq].index/360)
            
            for d in zero_df.loc[compound_freq+90:].index:
                d_prev = d - 90
                bootstrap_pv = 0
                int_payment = df.loc[d] * (90/360) /100
                while d_prev>0:
                    bootstrap_pv += int_payment * self.discount_factor.loc[d_prev]
                    d_prev -= 90
                    
                self.discount_factor.loc[d] = (1 - bootstrap_pv) /(1 + int_payment)
                zero_df.loc[d] = (pow(1/self.discount_factor.loc[d],360/d) -1 ) * 100 
            
            return zero_df
    
        def FwdCurve(df):
            fwd_df = pd.Series(index=np.arange(0,self.max_dtm,90),name='Rate')
            fwd_df.loc[0] = df.loc[90]
            
            for d in np.arange(90,self.max_dtm,90):
                fwd_df.loc[d] = (pow(pow((1+df.loc[d+90]/100),(d+90)/360) / pow((1+df.loc[d]/100),(d)/360),4) - 1 ) * 100
            
            return fwd_df
            
        self.yield_curve = Interpolate3M(curve_df.set_index('Dtm')['Rate'])
        self.discount_factor = pd.Series(index=self.yield_curve.index,name='Rate')
        self.zero_curve = ZeroCurve(self.yield_curve)
        self.fwd_curve = FwdCurve(self.zero_curve)
        
    def Interpolate(self,curve,dtm):
        df_to_interpolate = getattr(self,curve)
        return pd.Series(np.interp(dtm,df_to_interpolate.index,list(df_to_interpolate)),index=[dtm],name='Rate')
    
    def Curve2Discount(self,curve,dtm):
        return np.reciprocal(np.power((1+np.array(curve)/100),np.array(dtm)/360))
    
    def CurveShift(self,shift):
        curve_df = copy.deepcopy(self.curve_df)
        curve_df['Rate'] = curve_df['Rate'] + shift/10000
        return Curve(curve_df,self.compound_freq)

class IRS:
    
    def __init__(self,fwd_curve,discount_curve,notional,today,start_date,end_date,amortisation_type='Constant',amortisation_schedule=None):
        self.fwd_curve= fwd_curve
        self.discount_curve = discount_curve
        self.notional  = notional
        self.today = today
        self.start_date = start_date
        self.end_date = end_date
        self.amortisation_type= amortisation_type
        
                
        def ScheduleGenerator(self):
            schedule = list()
            schedule.append(self.start_date)
            new_date = self.start_date + relativedelta(months=3)
            while new_date <= self.end_date:
                schedule.append(new_date)
                new_date += relativedelta(months=3)
            return schedule
        
        self.date_schedule = ScheduleGenerator(self)
        self.num_of_payments = len(self.date_schedule)-1    
        
        if self.amortisation_type =='Constant':
            self.amortisation_schedule = [notional for i in range(self.num_of_payments)]
        elif self.amortisation_type =='Linear':
            self.amortisation_schedule = [notional - (i/self.num_of_payments)*notional for i in range(self.num_of_payments)]
        elif self.amortisation_type =='Custom':
            self.amortisation_schedule  = amortisation_schedule

            
    def CalculateValue(self,par):
        df = pd.DataFrame(index = range(self.num_of_payments),columns=['Period_Start','Period_End','Dtm','Notional','Reset_Rate','Zero_Rate','Discount_Factor',
                                   'Interest_Payment_Float','Payment_PV','Fixed_Rate','Fixed_Payment',
                                   'Fixed_Payment_PV'])
        df.Period_Start = self.date_schedule[:-1]
        df.Period_End = self.date_schedule[1:]
        df.Dtm = (df.Period_End - self.today).dt.days
        df.Notional = self.amortisation_schedule
        df = df[df.Dtm>=0]
        df.Reset_Rate  = list(self.fwd_curve.Interpolate('fwd_curve',df.Dtm))
        df.Zero_Rate = list(self.discount_curve.Interpolate('zero_curve',df.Dtm))
        df.Discount_Factor= list(self.discount_curve.Curve2Discount(df.Zero_Rate,df.Dtm))
        df.Interest_Payment_Float = df.Notional * df.Reset_Rate/100 * (90/360)
        df.Payment_PV = df.Interest_Payment_Float * df.Discount_Factor
        df.Fixed_Rate = np.ones(len(df))*par
        df.Fixed_Payment = df.Notional * df.Fixed_Rate/100 * (90/360)
        df.Fixed_Payment_PV = df.Fixed_Payment * df.Discount_Factor

        
        return df.Payment_PV.sum() - df.Fixed_Payment_PV.sum() 
    
    def CalculatePar(self):
        
        r0=1
        pv = lambda r: self.CalculateValue(r)
        #res= opt.minimize(pv, r0, method="BFGS",options={'gtol': 1e-2})
        res= opt.root(pv, r0, method="hybr")
        #print(res)
        
        return res.x[0]
    
        

### main
def main():
    today= pd.to_datetime('2019/11/04',dayfirst=False)
    
    #read libor curve
    libor_df = pd.read_csv('libor.csv')
    
    #Libor curve object
    Libor = Curve(libor_df,compound_freq = 180)
    
    #fwd_starting 1yr IRS with linear amortisation
    start_date = pd.to_datetime('2019/12/01',dayfirst=False)
    end_date =  pd.to_datetime('2020/12/01',dayfirst=False)
    usd_irs1 = IRS(Libor,Libor,10000000,today,start_date,end_date,'Linear')
    usd_irs1_price = usd_irs1.CalculatePar()
    
    #fwd_starting 20yr IRS with no amortisation
    start_date = pd.to_datetime('2019/12/01',dayfirst=False)
    end_date =  pd.to_datetime('2039/12/01',dayfirst=False)
    usd_irs2 = IRS(Libor,Libor,10000000,today,start_date,end_date,'Constant')
    usd_irs2_price = usd_irs2.CalculatePar()
    
    #already started 20yr IRS with no amortisation
    start_date = pd.to_datetime('2018/12/01',dayfirst=False)
    end_date =  pd.to_datetime('2039/12/01',dayfirst=False)
    usd_irs3 = IRS(Libor,Libor,10000000,today,start_date,end_date,'Constant')
    usd_irs3_price = usd_irs3.CalculatePar()
    usd_irs3_value = usd_irs3.CalculateValue(2.1)

### start main
if __name__ == "__main__":
    main()