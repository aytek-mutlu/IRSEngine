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
    '''
    Curve object: 
        Object accepts swap yield curve with respective days to maturity 
        and its compounding frequency as input.
        
        Assumptions:
            Day count: 30/360
            Ignore holidays, weekends
        
        Object attributes:
            yield_curve
            zero_curve
            fwd_curve
            discount_factor
            
        Object methods:
            Interpolate:      Linear interpolation of broken days from a given curve
            Curve2Discount:   Conversion of any given zero curve to discount factors
            CurveShift:       Curve shift of any given Curve object by specified basis points
    '''
    
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
    '''
    Curve object: 
        Object accepts forward curve, discount curve, initial notional, start and end dates, 
        amortisation type, amortisation schedule if needed as input
        
        Object attributes:
            fwd_curve
            discount_curve
            notional
            today
            start_date
            end_date
            amortisation_type
            date_schedule
            num_of_payments
            amortisation_schedule
            
        Object methods:
            CalculateValue:      Calculation of present value of any given already issued swap
            CalculatePar:        Calculation of par value of any given new swap
    '''
    
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
            if len(amortisation_schedule)==self.num_of_payments:
                self.amortisation_schedule  = amortisation_schedule
            else:
                print('Amortisation schedule is not suitable with the given swap parameters. Linear amortisation is applied instead')
                self.amortisation_schedule = [notional - (i/self.num_of_payments)*notional for i in range(self.num_of_payments)]

            
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
        res= opt.root(pv, r0, method="hybr")        
        return res.x[0]
    
        

### main
def main():
    today= pd.to_datetime('2019/11/04',dayfirst=False)
    
    #read curves
    us_libor_df = pd.read_csv(r'Curves/US_LIBOR.csv')
    us_ois_df = pd.read_csv(r'Curves/US_OIS.csv')
    euribor_df = pd.read_csv(r'Curves/EURIBOR.csv')
    eur_ois_df = pd.read_csv(r'Curves/EUR_OIS.csv')    
    
    #curve objects
    US_Libor = Curve(us_libor_df,compound_freq = 180)
    US_OIS = Curve(us_ois_df,compound_freq = 1)
    Euribor = Curve(euribor_df,compound_freq = 180)
    EUR_OIS = Curve(eur_ois_df,compound_freq = 1)    
    
    #already issued swap with 1.5 years of remaining maturity
    start_date = pd.to_datetime('2019/06/01',dayfirst=False)
    end_date =  pd.to_datetime('2020/12/01',dayfirst=False)
    usd_irs1 = IRS(US_Libor,US_OIS,10000000,today,start_date,end_date,amortisation_type='Constant')
    usd_irs1_value = usd_irs1.CalculateValue(par=3)
    
    #already issued swap with 1.5 years of remaining maturity with custom amortisation schedule
    start_date = pd.to_datetime('2019/06/01',dayfirst=False)
    end_date =  pd.to_datetime('2021/06/01',dayfirst=False)
    notional  = 10000000
    schedule = [notional,notional*7/8,notional*3/4,notional*5/8,notional*1/2,
                notional*3/8,notional*1/4,notional*1/8]
    usd_irs2 = IRS(Libor,Libor,notional,today,start_date,end_date,amortisation_type='Custom',
                   amortisation_schedule=schedule)
    usd_irs2_value = usd_irs2.CalculateValue(par=3)
    
    
    #spot starting swap with 5 years of maturity and linear amortisation
    start_date = pd.to_datetime('2019/11/06',dayfirst=False)
    end_date =  pd.to_datetime('2024/11/06',dayfirst=False)
    usd_irs3 = IRS(Libor,Libor,10000000,today,start_date,end_date,amortisation_type='Linear')
    usd_irs3_price = usd_irs3.CalculatePar()
    
   
    
    #already started 20yr IRS with no amortisation and fixed rate of 2.1%
    start_date = pd.to_datetime('2018/12/01',dayfirst=False)
    end_date =  pd.to_datetime('2039/12/01',dayfirst=False)
    usd_irs4 = IRS(Libor,Libor,10000000,today,start_date,end_date,'Constant')
    usd_irs4_value = usd_irs4.CalculateValue(2.1)
    
    Libor_100_up  = Libor.CurveShift(100)
    Libor_100_down  = Libor.CurveShift(-100)
    
    usd_irs4_price_delta_up  = IRS(Libor_100_up,Libor,10000000,today,start_date,end_date,'Constant').CalculateValue(2.1)- usd_irs4_value
    usd_irs4_price_delta_down  = IRS(Libor_100_down,Libor,10000000,today,start_date,end_date,'Constant').CalculateValue(2.1)- usd_irs4_value    

### start main
if __name__ == "__main__":
    main()