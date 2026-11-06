"""
Data models for FD Rate Sync & Audit System.
Using Pydantic v2 for data validation, serialization, and clean JSON outputs.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RateSlab(BaseModel):
    tenure: str = Field(description="Human readable tenure string, e.g. '1 Year to < 15 Months'")
    min_days: Optional[int] = Field(default=None, description="Normalized lower bound in days")
    max_days: Optional[int] = Field(default=None, description="Normalized upper bound in days")
    etm_gen: Optional[float] = Field(default=None, description="ET Money General Rate")
    etm_sr: Optional[float] = Field(default=None, description="ET Money Senior Citizen Rate")
    off_gen: Optional[float] = Field(default=None, description="Official General Rate")
    off_sr: Optional[float] = Field(default=None, description="Official Senior Citizen Rate")
    status: str = Field(default="IN_SYNC", description="IN_SYNC | RATE_HIKE | RATE_CUT | NEW_SLAB")
    change_details: str = Field(default="In Sync", description="Descriptive diff remark")

    # Helper aliases for backwards compatibility with existing dataset JSON
    def to_dataset_row(self) -> Dict[str, Any]:
        return {
            "Tenure": self.tenure,
            "ETM_Gen": f"{self.etm_gen:.2f}%" if self.etm_gen is not None else "--",
            "ETM_Sr": f"{self.etm_sr:.2f}%" if self.etm_sr is not None else "--",
            "Off_Gen": f"{self.off_gen:.2f}%" if self.off_gen is not None else "--",
            "Off_Sr": f"{self.off_sr:.2f}%" if self.off_sr is not None else "--",
            "Status": self.status,
            "ChangeDetails": self.change_details
        }


class DepositTable(BaseModel):
    table_title: str
    tier: str = Field(default="Retail (< 3 Cr)", description="Retail (< 3 Cr) or Bulk (>= 3 Cr)")
    etm_updated: str = Field(default="", description="ET Money heading / updated date")
    official_updated: str = Field(default="", description="Official w.e.f. date")
    official_link: str = Field(default="")
    rows: List[RateSlab] = Field(default_factory=list)
    has_changes: bool = False

    def to_dataset_table(self) -> Dict[str, Any]:
        return {
            "TableTitle": self.table_title,
            "ETMoneyUpdated": self.etm_updated,
            "OfficialUpdated": self.official_updated,
            "OfficialLink": self.official_link,
            "Rows": [r.to_dataset_row() for r in self.rows]
        }


class BankRecord(BaseModel):
    bank_name: str
    category: str = Field(default="Public Sector Bank")
    strapi_id: Optional[int] = None
    partner_type: Optional[int] = None
    etm_url: str = ""
    official_url_retail: str = ""
    official_url_bulk: Optional[str] = None
    has_bulk_table: bool = False
    tables: List[DepositTable] = Field(default_factory=list)

    def to_dataset_bank(self) -> Dict[str, Any]:
        return {
            "Bank": self.bank_name,
            "Category": self.category,
            "ETMoneyUrl": self.etm_url,
            "OfficialUrl": self.official_url_retail,
            "Tables": [t.to_dataset_table() for t in self.tables]
        }


class ContradictionItem(BaseModel):
    bank_name: str
    field_name: str
    issue_type: str
    detected_value: str
    expected_value: str
    snippet: str


class AuditSummary(BaseModel):
    generated_at: str
    total_banks: int
    changed_banks: List[str]
    total_hikes: int
    total_cuts: int
    total_new_slabs: int
    contradictions: List[ContradictionItem] = Field(default_factory=list)
