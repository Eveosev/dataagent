"""Aggregate service inputs; host context never appears in tool arguments."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from dataagent_contracts.intake import SourceSelection
from dataagent_contracts.ontology import MappingSpec,ReviewDecision
from .document_fields import DocumentField


class Input(BaseModel):
    model_config=ConfigDict(extra='forbid')


class Start(Input):
    goal:str=Field(min_length=1)
    sources:list[SourceSelection]=Field(min_length=1)


class Session(Input):
    session_id:str


class Propose(Session):
    proposal:MappingSpec
    expected_revision:str


class ProposeSources(Session):
    proposals: dict[str, MappingSpec] = Field(min_length=1)
    expected_revision: str


class Apply(Session):
    decision:ReviewDecision
    expected_revision:str


class Extract(Session):
    source_id: str
    expected_revision: str
    fields: list[DocumentField] = Field(min_length=1, max_length=100)


class WorkflowCall(Input):
    operation: Literal['environment_discover', 'environment_observe_web', 'environment_web_observation',
                       'workflow_draft', 'workflow_submit_proposal',
                       'workflow_start', 'workflow_advance', 'workflow_status',
                       'workflow_control', 'workflow_actions', 'workflow_waits']
    arguments: dict


class WorkflowView(Input):
    run_id: str


MODELS={'intake_start':Start,**{name:Session for name in ['intake_status','intake_advance','intake_inference','mapping_preview','workbench_view']},
    'intake_propose':Propose,'intake_propose_sources':ProposeSources,'mapping_apply':Apply,'intake_extract':Extract,
    'workflow_call':WorkflowCall,'workflow_view':WorkflowView}
DESCRIPTIONS={'intake_start':'建立来源和业务目标，返回持久任务与作业',
    'intake_advance':'自动识别和探查来源，返回映射所需的获准样本与目标',
    'intake_inference':'读取经披露范围过滤的映射提案请求',
    'intake_extract':'将已观察 PDF 的原文片段提取为有精确锚点的新字段',
    'intake_propose':'提交结构化映射；组件验证和试算，不直接发布',
    'intake_propose_sources':'按来源 ID 提交所有映射，一起验证并试算同一组本体对象',
    'mapping_preview':'读取当前预览修订、数量与问题摘要',
    'mapping_apply':'对当前预览保存明确范围的决定，拒绝过期修订',
    'intake_status':'查询当前任务修订与阶段','workbench_view':'打开同一任务的本地工作台',
    'workflow_call':'探查宿主配置的业务环境，提交、推进或查看已验证的流程和动作回执',
    'workflow_view':'在本地浏览器查看已登记工作流的执行状态'}
TOOLS=[{'name':name,'description':DESCRIPTIONS[name],'inputSchema':model.model_json_schema()} for name,model in MODELS.items()]
