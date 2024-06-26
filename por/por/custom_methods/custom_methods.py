import math
import frappe
from frappe.utils import time_diff_in_hours
from datetime import datetime

def get_por_settings():
    settings = frappe.get_single('POR Settings')
    if settings:
        return settings
    else:
        frappe.throw('POR Settings not found. Please configure them in the POR Settings doctype.')



def calculate_rate_and_uom(doc, method):
    settings = get_por_settings()
    for item in doc.items:
        if item.date_out and item.date_returned:  # Simplified attribute check
            date_out = datetime.strptime(item.date_out, '%Y-%m-%d %H:%M:%S')
            date_returned = datetime.strptime(item.date_returned, '%Y-%m-%d %H:%M:%S')
            duration = (date_returned - date_out).total_seconds() / 3600.0

            # set the rates
            overage_rate = frappe.get_value("Item Price", {"item_code": item.item_code, "uom": "Daily"}, "price_list_rate") // settings.daily_divisor
            daily_rate = frappe.get_value("Item Price", {"item_code": item.item_code, "uom": "Daily"}, "price_list_rate")
            weekly_rate = frappe.get_value("Item Price", {"item_code": item.item_code, "uom": "Weekly"}, "price_list_rate")
            four_week_rate = frappe.get_value("Item Price", {"item_code": item.item_code, "uom": "4Week"}, "price_list_rate")

            # vars for multiple calculations
            full_days = int(duration / 24)
            daily_amount = full_days * daily_rate
            remainder_hours = duration % 24
            extra_hours = remainder_hours - settings.daily_grace
            rounded_hours = math.ceil(extra_hours)
            four_hour_chunks = (rounded_hours + settings.overage_billing_interval - 1) // settings.overage_billing_interval
            extra_charge = four_hour_chunks * overage_rate

            # calculate for half day rate when returned on time
            if duration <= (4 + settings.four_hr_grace):
                rate = frappe.get_value("Item Price", {"item_code": item.item_code, "uom": "4hr"}, "price_list_rate")
                uom = '4hr'
                rental_units = '4hr 1'              

            # calculate between 4-24 hours    
            elif duration <= (24 + settings.daily_grace):
                rate = daily_rate
                uom = 'Daily'
                rental_units = 'D 1'

            # calculate up to three days    
            elif duration <= (72 + settings.daily_grace):
                rate = daily_amount + extra_charge
                uom = 'Daily'
                rental_units = f"D {full_days}, OT {rounded_hours}"

            # calculate 3 days to one week
            elif duration <= (168 + settings.daily_grace):
                rate = weekly_rate
                uom = 'Weekly'
                rental_units = 'Wk 1'

            # calculate more than one week, less than two weeks    
            elif duration <= 236:
                hours_remaining = duration - 168
                full_days = int(hours_remaining / 24)
                remainder_hours = duration - (full_days * 24)
                #had to change calculation below. Order of variables matters. Could not simply use daily_amount it used too many days
                rate = weekly_rate + (daily_rate * full_days) + (extra_charge if extra_hours > 0 else 0)
                uom = 'Weekly'
                #rental_units = f"Wk ew 1, wkRate {weekly_rate}, D {full_days}, dAmt {daily_amount} OT {rounded_hours} extra {extra_charge}"
                rental_units = f"Wk 1, D {full_days}, OT {rounded_hours}"

            #calculate 4Week rate when greater than two weeks and <= 28 days
            elif duration <=  (672 + settings.daily_grace):
                rate = four_week_rate 
                uom = '4Week'
                rental_units = "4Wk 1"  
            
            # calculate all cases greater than 28 days
            else:
                four_week_chunks = int(duration / 672)
                remainder_hours = duration % 672

                # case when greater than four weeks + three days or less
                if remainder_hours <= (72 + settings.daily_grace):
                    full_days = int(remainder_hours / 24)
                    extra_hours = remainder_hours - (full_days * 24) - settings.daily_grace
                    rate = (four_week_rate * four_week_chunks) + (full_days * daily_rate) + extra_charge
                    uom = '4Week'
                    rental_units = f"4Wk {four_week_chunks}, D {full_days}, OT {rounded_hours}"

                # case when rounding to five weeks
                elif remainder_hours <=  (168 + settings.daily_grace):
                    rate =  (four_week_rate * four_week_chunks) + weekly_rate
                    uom = '4Week'
                    rental_units = "4Wk 1, Wk 1"

                # calculate monthly plus weekly rate and up to three days remaining before adding additional 4week    
                elif remainder_hours <= 236:
                    hours_remaining = remainder_hours - 168
                    full_days = int(hours_remaining / 24)
                    extra_hours = hours_remaining - (full_days * 24) - settings.daily_grace
                    rate = (four_week_chunks * four_week_rate) + (full_days * daily_rate) + weekly_rate + (extra_charge if extra_hours > 0 else 0)
                    uom = '4Week'
                    rental_units = f"4Wk {four_week_chunks}, Wk 1, D {full_days}, OT {rounded_hours}"


                elif remainder_hours > 236:
                    rate = ((four_week_chunks +1) * four_week_rate) 
                    uom = '4Week' 
                    rental_units = f"4Wk {four_week_chunks +1}"  


            item.rate = rate  # Set rate explicitly calculated every time
            item.uom = uom
            item.rental_uom = rental_units

    doc.calculate_taxes_and_totals()
