"""
Pydantic schemas for technical analysis visualization data.
Following Alpha-Guardian Constitution Principle III: Strict schema enforcement.
"""
from typing import List, Optional, Literal, Dict, Union
from pydantic import BaseModel, Field

class ChartPoint(BaseModel):
    """Represents a single OHLC data point."""
    time: str = Field(..., description="Timestamp in ISO 8601 or YYYY-MM-DD format")
    open: float
    high: float
    low: float
    close: float

class VolumePoint(BaseModel):
    """Represents a single volume data point."""
    time: str
    value: float
    color: Optional[str] = Field(None, description="Hex color for the volume bar")

class IndicatorStyle(BaseModel):
    """Visual style for a technical indicator."""
    color: str
    lineWidth: Optional[int] = 2
    areaColor: Optional[str] = None

class DataPoint(BaseModel):
    """A generic data point for indicator series."""
    time: str
    value: float

class Indicator(BaseModel):
    """Metadata and series data for a technical indicator."""
    id: str
    name: str
    pane: Literal["main", "sub"]
    type: Literal["line", "area", "histogram"]
    style: IndicatorStyle
    data: List[DataPoint]

class AnalysisMarker(BaseModel):
    """Visual anchor for AI explicability."""
    time: str
    text: str
    position: Literal["aboveBar", "belowBar", "inBar"]
    shape: Literal["arrowUp", "arrowDown", "circle", "square"]
    color: str

class VisualizationData(BaseModel):
    """Root container for technical analysis visualization."""
    ticker: str
    ohlc: List[ChartPoint]
    volume: List[VolumePoint]
    indicators: List[Indicator]
    markers: List[AnalysisMarker]
