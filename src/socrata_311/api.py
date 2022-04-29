# -*- coding: utf-8 -*-
"""
Created on Mon Jul 31 21:52:56 2017

@author: romulo
"""
from sodapy import Socrata
from . import settings, etl
import pandas as pd
import datetime

# =============================================================================
#   receives a date object or timestamp in isoformat
#   an existing connection is optional, can create a new one
#   beware of the restrictive optional parameters (timeout, data limit)
#   can be used to simply pull data modified in Socrata since a given timestamp
# =============================================================================
def pull_data_modified_since(since,client=None,timeout = 120,data_limit = 10000):
    if client is None:
        client = Socrata(settings.APP_NYC_API_DOMAIN ,settings.APP_TOKEN_311,timeout=timeout)
    return client.get(
        settings.APP_NYC_DATASET,
        limit=data_limit,
        where="resolution_action_updated_date >= '" + str(since) + "'",
    )

# =============================================================================
#   receives a date object or timestamp in isoformat
#   an existing connection is optional, can create a new one
#   beware of the restrictive optional parameters (timeout, data limit)
#   can be used to simply pull data created in Socrata since a given timestamp
# =============================================================================
def pull_data_created_since(since,client=None,timeout = 120,data_limit = 10000):
    if client is None:
        client = Socrata(settings.APP_NYC_API_DOMAIN ,settings.APP_TOKEN_311,timeout=timeout)
    return client.get(
        settings.APP_NYC_DATASET,
        limit=data_limit,
        where="created_date>= '" + str(since) + "'",
    )


# =============================================================================
#   receives a date object or timestamp in isoformat
#   an existing connection is optional, can create a new one
#   beware of the restrictive optional parameters (timeout)
#   The main purpose of this method is to return the percentage closure stats
#   for a given group key
# =============================================================================
def pull_agg_closure_statistics_created_since(since,client=None,timeout = 120,group_key = ['agency'], restrict_clause=""):
    if client is None:
        client = Socrata(settings.APP_NYC_API_DOMAIN ,settings.APP_TOKEN_311,timeout=timeout)
    group_key_str = ','.join(group_key)
    where_clause = " and " + restrict_clause if (restrict_clause != "") else ""
    data = client.get(
        settings.APP_NYC_DATASET,
        query=(
            (
                (
                    (
                        (
                            f"select {group_key_str}" + ", "
                            "count(*) as total, "
                            "sum(case(status='Closed',1,true,0)) as closed "
                            "where created_date>= '"
                        )
                        + str(since)
                        + "'"
                    )
                    + where_clause
                )
                + " group by "
            )
            + group_key_str
        ),
    )


    dataFrame= pd.DataFrame.from_dict(data)
    dataFrame['perc_closed'] = (dataFrame['closed'].astype('float') / dataFrame['total'].astype('float'))
    return dataFrame


# =============================================================================
#   receives a date object or timestamp in isoformat
#   an existing connection is optional, can create a new one
#   beware of the restrictive optional parameters (timeout, data limit)
#   Not widely used due to the vasts amounts of data pulled (not restrictive enough)
#   but this method essentially pulls the raw data in addition to a time to closure
#   calc
# =============================================================================
def pull_raw_time_to_closure_statistics_created_since_closed_only(since,client=None,timeout = 120,group_key = ['agency'], data_limit = 1000):
    if client is None:
        client = Socrata(settings.APP_NYC_API_DOMAIN ,settings.APP_TOKEN_311,timeout=timeout)
    group_key_str = ','.join(group_key)

    data = client.get(settings.APP_NYC_DATASET,limit = data_limit,where = "created_date >= '"+str(since)+"'" +
                      " and closed_date IS NOT NULL and status = 'Closed'",
                      select = group_key_str+",closed_date,created_date,"\
                          "(date_extract_woy(closed_date)*7) -(7 - case(date_extract_dow(closed_date)=0,7,true,date_extract_dow(closed_date))) as closed_doy," \
                          "(date_extract_woy(created_date)*7) - (7 - case(date_extract_dow(closed_date)=0,7,true,date_extract_dow(created_date))) as created_doy,"\
                          "(date_extract_y(closed_date)  - date_extract_y(created_date)) * 365 as year_diff_adjustment,"\
                          #"(date_extract_woy(closed_date)*7) as closed_woy,(date_extract_woy(created_date)*7) as created_woy")
                          "closed_doy - created_doy + year_diff_adjustment as days_to_closure")
    list(map(lambda x: etl.calculate_days_to_closure_dict(x), data))
    dataFrame= pd.DataFrame.from_dict(data)
    dataFrame['days_to_closure'] = dataFrame['days_to_closure'].astype('float')
    return dataFrame

# =============================================================================
#   receives a date object or timestamp in isoformat
#   an existing connection is optional, can create a new one
#   beware of the restrictive optional parameters (timeout, data limit)
#   This method calculates the average time to closure per group key for
#   all complaints received since the desired timestamp
# =============================================================================
def pull_agg_time_to_closure_statistics_created_since_closed_only(since,client=None,timeout = 120,group_key = ['agency']):
    if client is None:
        client = Socrata(settings.APP_NYC_API_DOMAIN ,settings.APP_TOKEN_311,timeout=timeout)
    group_key_str = ','.join(group_key)

    data = client.get(
        settings.APP_NYC_DATASET,
        query=(
            (
                (
                    f"select {group_key_str}" + ","
                    "avg(((date_extract_woy(closed_date)*7) -(7 - case(date_extract_dow(closed_date)=0,7,true,date_extract_dow(closed_date)))) "
                    " - ((date_extract_woy(created_date)*7) - (7 - case(date_extract_dow(created_date)=0,7,true,date_extract_dow(created_date)))) "
                    " + ((date_extract_y(closed_date)  - date_extract_y(created_date))* 365) "
                    ") as days_to_closure "
                    "where created_date >= '"
                )
                + str(since)
                + "' and closed_date IS NOT NULL and status = 'Closed' "
                "group by "
            )
            + group_key_str
        ),
    )

    dataFrame= pd.DataFrame.from_dict(data)
    dataFrame['days_to_closure'] = dataFrame['days_to_closure'].astype('float')
    return dataFrame

# =============================================================================
#   receives a date object or timestamp in isoformat
#   an existing connection is optional, can create a new one
#   beware of the restrictive optional parameters (timeout, data limit)
#   This method calculates the average time to closure per group key for
#   all complaints received since the desired timestamp and combines it with the
#   percentage closed ratio metrics
# =============================================================================
def pull_full_closure_statistics_since_date(since,client=None,timeout = 120,group_key = ['agency']):
    aggWithTimeToClosure = pull_agg_time_to_closure_statistics_created_since_closed_only(since,timeout=timeout,group_key = group_key)
    aggWithPercClosed = pull_agg_closure_statistics_created_since(since,timeout=timeout,group_key=group_key)
    consolidated = aggWithPercClosed.merge(aggWithTimeToClosure,how='left',on=group_key,suffixes=('_perc','_ttc'))
    consolidated['created_after_timestamp'] = since
    return consolidated

# =============================================================================
#   an existing connection is optional, can create a new one
#   beware of the restrictive optional parameters (timeout, data limit)
#   This method calculates the average time to closure per group key for
#   all complaints received since the desired number of weeks (in the past)
#  and combines it with the percentage closed ratio metrics
#  =============================================================================
def pull_full_closure_statistics_since_x_weeks(weeks,client=None,timeout = 120,group_key = ['agency']):
    st = datetime.datetime.now() - datetime.timedelta(weeks=weeks)
    since = st.isoformat()
    consolidated = pull_full_closure_statistics_since_date(since,timeout=timeout,group_key=group_key)
    consolidated['past_number_of_weeks'] = weeks
    return consolidated

# =============================================================================
#   an existing connection is optional, can create a new one
#   beware of the restrictive optional parameters (timeout, data limit)
#   This method returns groupings of the passed key (granularity) and number of days
#   to closure, the main idea is to use it to generate histograms and dive into a specific
#   type of complaints
#  =============================================================================
def pull_daily_closure_statistics_since_x_weeks(weeks, client=None, timeout=120,group_key=['agency'], data_limit=10000
                                                ,restrict_clause = ""):
    st = datetime.datetime.now() - datetime.timedelta(weeks=weeks)
    since = st.isoformat()
    if client is None:
        client = Socrata(settings.APP_NYC_API_DOMAIN, settings.APP_TOKEN_311, timeout=timeout)
    group_key_str = ','.join(group_key)
    where_clause = " and "+restrict_clause if (restrict_clause != "") else ""
    data = client.get(
        settings.APP_NYC_DATASET,
        query=(
            (
                (
                    (
                        (
                            (
                                f"select {group_key_str}" + ","
                                "(((date_extract_woy(closed_date)*7) -(7 - case(date_extract_dow(closed_date)=0,7,true,date_extract_dow(closed_date)))) "
                                " - ((date_extract_woy(created_date)*7) - (7 - case(date_extract_dow(created_date)=0,7,true,date_extract_dow(created_date)))) "
                                " + ((date_extract_y(closed_date)  - date_extract_y(created_date))* 365) "
                                ") as days_to_closure, count(unique_key) as number_of_records "
                                "where created_date >= '"
                            )
                            + str(since)
                            + "' and closed_date IS NOT NULL and status = 'Closed' "
                        )
                        + where_clause
                    )
                    + " group by "
                )
                + group_key_str
            )
            + ", days_to_closure"
        ),
    )

    dataFrame = pd.DataFrame.from_dict(data)
    dataFrame['days_to_closure'] = dataFrame['days_to_closure'].astype('float')
    dataFrame['past_number_of_weeks'] = weeks
    dataFrame['created_after_timestamp'] = since
    return dataFrame

# =============================================================================
#
#   This method returns the ratio of complaints closed within a day! (for those actually closed)
#
# =============================================================================
def pull_closed_within_a_day_stats_since_x_weeks(weeks, client=None, timeout=120,group_key=['agency'], data_limit=10000
                                                 , restrict_clause=""):
    st = datetime.datetime.now() - datetime.timedelta(weeks=weeks)
    since = st.isoformat()
    if client is None:
        client = Socrata(settings.APP_NYC_API_DOMAIN, settings.APP_TOKEN_311, timeout=timeout)
    group_key_str = ','.join(group_key)
    where_clause = " and " + restrict_clause if (restrict_clause != "") else ""
    data = client.get(
        settings.APP_NYC_DATASET,
        query=(
            (
                (
                    (
                        (
                            f"select {group_key_str}" + ","
                            "avg(case((((date_extract_woy(closed_date)*7) -(7 - case(date_extract_dow(closed_date)=0,7,true,date_extract_dow(closed_date)))) "
                            " - ((date_extract_woy(created_date)*7) - (7 - case(date_extract_dow(created_date)=0,7,true,date_extract_dow(created_date)))) "
                            " + ((date_extract_y(closed_date)  - date_extract_y(created_date))* 365) "
                            ")<=1,1,true,0 )) as closed_within_a_day, count(unique_key) as number_of_records "
                            "where created_date >= '"
                        )
                        + str(since)
                        + "' and closed_date IS NOT NULL and status = 'Closed' "
                    )
                    + where_clause
                )
                + " group by "
            )
            + group_key_str
        ),
    )

    dataFrame = pd.DataFrame.from_dict(data)
    dataFrame['closed_within_a_day'] = dataFrame['closed_within_a_day'].astype('float')
    dataFrame['past_number_of_weeks'] = weeks
    dataFrame['created_after_timestamp'] = since
    #adding non-closed items as well
    aggWithPercClosed = pull_agg_closure_statistics_created_since(since, timeout=timeout, group_key=group_key,restrict_clause=restrict_clause)
    consolidated = aggWithPercClosed.merge(dataFrame, how='left', on=group_key, suffixes=('_perc', '_closed'))
    consolidated['overall_closed_within_a_day'] = (consolidated['closed_within_a_day']*consolidated['perc_closed'])
    return consolidated
