# -*- coding: utf-8 -*-
"""
Created on Mon Nov  4 11:23:25 2019

@author: aytekm
"""

import pandas as pd
import numpy as np

class Curve:
    
    def __init__(self, curve_df,compound_freq):
        
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
        

class IRS:
    def __init__(self,fwd_curve,discount_curve,notional,today,start_date,end_date,amortisation_type='Constant',amortisation_schedule=None):
        self.fwd_curve= fwd_curve
        self.discount_curve = discount_curve
        self.notional  = notional
        self.today = today
        self.start_date = start_date
        self.end_date = end_date
        self.num_of_payments = (self.end_date - self.start_date).dt.days/90        
        self.amortisation_type= amortisation_type
        
        if self.amortisation_type =='Constant':
                self.amortisation_schedule = [notional for i in range(self.num_of_payments)]
        elif self.amortisation_type =='Linear':
                self.amortisation_schedule = [notional - (i/self.num_of_payments)*notional for i in range(self.num_of_payments)]
        elif self.amortisation_type =='Custom':
                self.amortisation_schedule  = amortisation_schedule
            
    def CalculatePar(self):
        df = pd.DataFrame(index = pd.date_range(start=self.start_date,end=self.end_date,periods=90),columns=['Dtm','Notional','Reset_Rate','Discount_Factor','Interest_Payment_Float','PV'])
        pass
    
    def CalculatePV():
        pass

### main
def main():
    
    #read libor curve
    libor_df = pd.read_csv('libor.csv')
    Libor = Curve(libor_df,compound_freq = 180)
    

### start main
if __name__ == "__main__":
    main()