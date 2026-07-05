import json
import logging
import re
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from .schemas import VisualizationData, ChartPoint, VolumePoint, Indicator, IndicatorStyle, DataPoint, AnalysisMarker

logger = logging.getLogger(__name__)

def normalize_ticker_for_yahoo(ticker: str) -> str:
    """Normalize ticker for Yahoo Finance (BR tickers need .SA suffix)"""
    if not ticker:
        return ""
    ticker_upper = ticker.upper().strip()
    
    # If already ends with .SA, return as is
    if ticker_upper.endswith(".SA"):
        return ticker_upper
        
    # If ends with .BR, replace with .SA
    if ticker_upper.endswith(".BR"):
        return ticker_upper[:-3] + ".SA"
        
    # If ends with .US, strip it (Yahoo Finance doesn't use .US suffix)
    if ticker_upper.endswith(".US"):
        return ticker_upper[:-3]
        
    # Check if it looks like a Brazilian ticker: e.g. PETR4, VALE3, BOVA11
    # 4 letters followed by 1 or 2 digits
    if re.match(r"^[A-Z]{4}\d{1,2}$", ticker_upper):
        return f"{ticker_upper}.SA"
        
    return ticker_upper

async def get_chart_data_internal(ticker: str, period: str = "1y") -> VisualizationData:
    """
    Fetches OHLC and Volume data, calculates mandatory indicators, 
    and returns a VisualizationData object.
    """
    logger.info(f"Fetching chart data for {ticker} (period={period})")
    
    # Map display period to a longer fetch period for indicator warm-up (e.g. SMA 200)
    now = datetime.now()
    if period == "1mo":
        start_date = now - timedelta(days=30)
        fetch_period = "1y"
    elif period == "3mo":
        start_date = now - timedelta(days=90)
        fetch_period = "1y"
    elif period == "6mo":
        start_date = now - timedelta(days=180)
        fetch_period = "2y"
    elif period == "1y":
        start_date = now - timedelta(days=365)
        fetch_period = "2y"
    elif period == "2y":
        start_date = now - timedelta(days=730)
        fetch_period = "5y"
    else:
        start_date = None
        fetch_period = period

    try:
        normalized_ticker = normalize_ticker_for_yahoo(ticker)
        stock = yf.Ticker(normalized_ticker)
        df = stock.history(period=fetch_period)
        
        if df is None or df.empty:
            raise ValueError(f"Ticker {ticker} not found or no data available.")
            
        start_date_str = start_date.strftime("%Y-%m-%d") if start_date else None
        logger.info(f"Loaded {len(df)} candles for {normalized_ticker}. Filtering display data from {start_date_str}")

        # Basic OHLC data
        ohlc_data = []
        volume_data = []
        
        for index, row in df.iterrows():
            timestamp = index.strftime("%Y-%m-%d")
            if start_date_str and timestamp < start_date_str:
                continue
            ohlc_data.append(ChartPoint(
                time=timestamp,
                open=float(row['Open']),
                high=float(row['High']),
                low=float(row['Low']),
                close=float(row['Close'])
            ))
            
            # Determine volume color (green if close > open, red otherwise)
            vol_color = "#26a69a" if row['Close'] >= row['Open'] else "#ef5350"
            volume_data.append(VolumePoint(
                time=timestamp,
                value=float(row['Volume']),
                color=vol_color
            ))
            
        # Mandatory Indicator Calculations on FULL dataframe (no NaN warmup issues)
        indicators = []
        markers = []
        
        # 1. Simple Moving Averages
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        
        # Add SMA 50
        if 'SMA_50' in df.columns:
            sma50_data = []
            for index, row in df.iterrows():
                timestamp = index.strftime("%Y-%m-%d")
                if start_date_str and timestamp < start_date_str:
                    continue
                if pd.notna(row['SMA_50']):
                    sma50_data.append(DataPoint(time=timestamp, value=float(row['SMA_50'])))
            
            indicators.append(Indicator(
                id="SMA_50",
                name="SMA (50)",
                pane="main",
                type="line",
                style=IndicatorStyle(color="#2962FF", lineWidth=2),
                data=sma50_data
            ))
            
        # Add SMA 200
        if 'SMA_200' in df.columns:
            sma200_data = []
            for index, row in df.iterrows():
                timestamp = index.strftime("%Y-%m-%d")
                if start_date_str and timestamp < start_date_str:
                    continue
                if pd.notna(row['SMA_200']):
                    sma200_data.append(DataPoint(time=timestamp, value=float(row['SMA_200'])))
            
            indicators.append(Indicator(
                id="SMA_200",
                name="SMA (200)",
                pane="main",
                type="line",
                style=IndicatorStyle(color="#FF6D00", lineWidth=2),
                data=sma200_data
            ))

        # Detect Crossovers (Golden Cross & Death Cross) on full dataset
        if 'SMA_50' in df.columns and 'SMA_200' in df.columns:
            valid_df = df[['SMA_50', 'SMA_200']].dropna()
            prev_sma50 = None
            prev_sma200 = None
            
            for index, row in valid_df.iterrows():
                val50 = float(row['SMA_50'])
                val200 = float(row['SMA_200'])
                timestamp = index.strftime("%Y-%m-%d")
                
                if prev_sma50 is not None and prev_sma200 is not None:
                    # Filter crossovers to display range
                    if not start_date_str or timestamp >= start_date_str:
                        # Golden Cross: SMA 50 crosses above SMA 200
                        if prev_sma50 <= prev_sma200 and val50 > val200:
                            markers.append(AnalysisMarker(
                                time=timestamp,
                                text="Golden Cross (Bullish)",
                                position="belowBar",
                                shape="arrowUp",
                                color="#26a69a"
                            ))
                        # Death Cross: SMA 50 crosses below SMA 200
                        elif prev_sma50 >= prev_sma200 and val50 < val200:
                            markers.append(AnalysisMarker(
                                time=timestamp,
                                text="Death Cross (Bearish)",
                                position="aboveBar",
                                shape="arrowDown",
                                color="#ef5350"
                            ))
                prev_sma50 = val50
                prev_sma200 = val200
            
        # 2. Bollinger Bands (20, 2)
        df.ta.bbands(length=20, std=2, append=True)
        bbu_col = next((col for col in df.columns if col.startswith("BBU_20_") or col.startswith("BBU_")), None)
        bbm_col = next((col for col in df.columns if col.startswith("BBM_20_") or col.startswith("BBM_")), None)
        bbl_col = next((col for col in df.columns if col.startswith("BBL_20_") or col.startswith("BBL_")), None)
        
        if bbu_col and bbm_col and bbl_col:
            bb_upper_data = []
            bb_middle_data = []
            bb_lower_data = []
            
            for index, row in df.iterrows():
                timestamp = index.strftime("%Y-%m-%d")
                if start_date_str and timestamp < start_date_str:
                    continue
                if pd.notna(row[bbu_col]):
                    bb_upper_data.append(DataPoint(time=timestamp, value=float(row[bbu_col])))
                if pd.notna(row[bbm_col]):
                    bb_middle_data.append(DataPoint(time=timestamp, value=float(row[bbm_col])))
                if pd.notna(row[bbl_col]):
                    bb_lower_data.append(DataPoint(time=timestamp, value=float(row[bbl_col])))
            
            indicators.append(Indicator(
                id="BB_Upper",
                name="BB Upper (20, 2)",
                pane="main",
                type="line",
                style=IndicatorStyle(color="#ab47bc", lineWidth=1),
                data=bb_upper_data
            ))
            indicators.append(Indicator(
                id="BB_Middle",
                name="BB Basis (20, 2)",
                pane="main",
                type="line",
                style=IndicatorStyle(color="#ba68c8", lineWidth=1),
                data=bb_middle_data
            ))
            indicators.append(Indicator(
                id="BB_Lower",
                name="BB Lower (20, 2)",
                pane="main",
                type="line",
                style=IndicatorStyle(color="#ab47bc", lineWidth=1),
                data=bb_lower_data
            ))

        # 3. Relative Strength Index (RSI 14)
        df.ta.rsi(length=14, append=True)
        if 'RSI_14' in df.columns:
            rsi_data = []
            for index, row in df.iterrows():
                timestamp = index.strftime("%Y-%m-%d")
                if start_date_str and timestamp < start_date_str:
                    continue
                if pd.notna(row['RSI_14']):
                    rsi_data.append(DataPoint(time=timestamp, value=float(row['RSI_14'])))
            
            indicators.append(Indicator(
                id="RSI_14",
                name="RSI (14)",
                pane="sub",
                type="line",
                style=IndicatorStyle(color="#00E5FF", lineWidth=2),
                data=rsi_data
            ))

        # 4. Moving Average Convergence Divergence (MACD 12, 26, 9)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        if 'MACD_12_26_9' in df.columns:
            macd_data = []
            for index, row in df.iterrows():
                timestamp = index.strftime("%Y-%m-%d")
                if start_date_str and timestamp < start_date_str:
                    continue
                if pd.notna(row['MACD_12_26_9']):
                    macd_data.append(DataPoint(time=timestamp, value=float(row['MACD_12_26_9'])))
            
            indicators.append(Indicator(
                id="MACD_12_26_9",
                name="MACD (12, 26, 9)",
                pane="sub",
                type="line",
                style=IndicatorStyle(color="#00C853", lineWidth=2),
                data=macd_data
            ))

        if 'MACDs_12_26_9' in df.columns:
            macds_data = []
            for index, row in df.iterrows():
                timestamp = index.strftime("%Y-%m-%d")
                if start_date_str and timestamp < start_date_str:
                    continue
                if pd.notna(row['MACDs_12_26_9']):
                    macds_data.append(DataPoint(time=timestamp, value=float(row['MACDs_12_26_9'])))
            
            indicators.append(Indicator(
                id="MACDs_12_26_9",
                name="MACD Signal",
                pane="sub",
                type="line",
                style=IndicatorStyle(color="#D500F9", lineWidth=2),
                data=macds_data
            ))

        if 'MACDh_12_26_9' in df.columns:
            macdh_data = []
            for index, row in df.iterrows():
                timestamp = index.strftime("%Y-%m-%d")
                if start_date_str and timestamp < start_date_str:
                    continue
                if pd.notna(row['MACDh_12_26_9']):
                    macdh_data.append(DataPoint(time=timestamp, value=float(row['MACDh_12_26_9'])))
            
            indicators.append(Indicator(
                id="MACDh_12_26_9",
                name="MACD Hist",
                pane="sub",
                type="histogram",
                style=IndicatorStyle(color="#B0BEC5", lineWidth=1),
                data=macdh_data
            ))
            
        return VisualizationData(
            ticker=ticker,
            ohlc=ohlc_data,
            volume=volume_data,
            indicators=indicators,
            markers=markers
        )
        
    except Exception as e:
        logger.error(f"Error generating chart data for {ticker}: {e}")
        raise
