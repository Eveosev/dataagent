"""Aggregate service inputs; host context never appears in tool arguments."""
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from dataagent_contracts.intake import SourceSelection
from dataagent_contracts.ontology import MappingSpec
from .document_fields import DocumentField
from .ontology_discovery import Mode, OntologyProposal
from .ontology_publish import PublishConfirm, PublishPrepare
from .query_service import OntologyInstancesSummary, OntologyQuery


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class StartTarget(Input):
    """Mapping target pinned on the task (D0)."""
    ontology_id: str = Field(min_length=1, description='目标本体 ID（已注册）')
    concept: str | None = Field(default=None, description='目标概念；单概念本体可省略')


class Start(Input):
    goal:str=Field(min_length=1)
    sources:list[SourceSelection]=Field(min_length=1)
    mode: Mode = "mapping"
    target: StartTarget | None = Field(default=None,
        description='映射目标（本体与概念）；缺省用内置采购本体的唯一概念')


class Session(Input):
    session_id:str


class Propose(Session):
    proposal:MappingSpec
    expected_revision:str


class ProposeSources(Session):
    proposals: dict[str, MappingSpec] = Field(min_length=1)
    expected_revision: str


class InstanceCorrection(Input):
    """Exact ``changes`` shape for target_scope=instance (FDE-4).

    The identifier key is ``entity_id``; a legacy ``entity`` key is rejected by
    the service and the error names the right key.
    """

    entity_id: str = Field(description='对象实例 ID，字段名必须是 entity_id（不是 entity）')
    property: str = Field(description='需要纠正的本体属性名')
    value: Any = Field(description='纠正后的值；按属性 value_type 校验')
    reason: str = Field(min_length=1, description='纠正原因，写入审计')


class MappingChanges(Input):
    """Explicit mapping decision payload for target_scope=mapping.

    Extra keys are accepted because a mapping proposal may grow before it is
    reviewed; the component still validates the mapping it receives.
    """

    model_config = ConfigDict(extra='allow')

    bindings: dict[str, Any] | None = Field(default=None, description='按目标属性提交 FieldBinding')
    relation_bindings: dict[str, dict[str, Any]] | None = Field(default=None, description='按关系角色提交 FieldBinding')
    unmapped: dict[str, Literal['extension', 'unresolved', 'exclude']] | None = Field(default=None)


class OntologyChanges(Input):
    """Explicit ontology draft payload for target_scope=ontology."""

    property: str = Field(description='待新增或修改的属性名')
    value_type: Literal['string', 'decimal', 'integer', 'boolean', 'date', 'datetime', 'reference']
    reason: str = ''


class InstanceDecision(Input):
    preview_ref: str
    target_scope: Literal['instance']
    changes: InstanceCorrection | None = None
    decision: Literal['save', 'reject'] = 'save'

    @model_validator(mode='after')
    def require_changes(self):
        if self.decision == 'save' and self.changes is None:
            raise ValueError('instance decisions need changes with entity_id/property/value/reason')
        return self


class MappingDecision(Input):
    preview_ref: str
    target_scope: Literal['mapping']
    changes: MappingChanges | None = None
    decision: Literal['save', 'reject'] = 'save'


class OntologyDecision(Input):
    preview_ref: str
    target_scope: Literal['ontology']
    changes: OntologyChanges | None = None
    decision: Literal['save', 'reject'] = 'save'

    @model_validator(mode='after')
    def require_changes(self):
        if self.decision == 'save' and self.changes is None:
            raise ValueError('ontology decisions need changes with property/value_type/reason')
        return self


Decision = Annotated[Union[InstanceDecision, MappingDecision, OntologyDecision],
                     Field(discriminator='target_scope')]


class Apply(Session):
    decision:Decision
    expected_revision:str
    allow_partial: bool = Field(default=False,
        description='保存时是否只放行无阻断的对象；冲突或缺必填的对象挂起，缺键记录单列')
    reason: str = Field(default='', description='部分保存的审计原因')


class Dispose(Session):
    expected_revision: str
    action: Literal['partition_not_applicable', 'exclude_record']
    source_id: str
    partition: int | str | None = Field(default=None,
        description='partition_not_applicable 必填：来源分区（如 PDF 页码）')
    record: int | None = Field(default=None, ge=0,
        description='exclude_record 必填：来源记录下标（0 起，如表头行）')
    reason: str = Field(min_length=1, description='处置原因，写入审计')

    @field_validator('reason')
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('处置原因不能为空')
        return value


class Inherit(Session):
    expected_revision: str
    decision_refs: list[str] = Field(default_factory=list,
        description='要继承的旧纠正 decision_ref；留空继承预览提示中的全部')


class Extract(Session):
    source_id: str
    expected_revision: str
    fields: list[DocumentField] = Field(min_length=1, max_length=100)


class DiscoveryPropose(Session):
    proposal: OntologyProposal
    expected_revision: str


class Registry(Input):
    include_deactivated: bool = Field(default=False,
        description='是否包含已停用本体（默认不列）')


class SourceConnections(Input):
    pass


class WorkflowCall(Input):
    operation: Literal['environment_discover', 'environment_observe_web', 'environment_web_observation',
                       'workflow_draft', 'workflow_submit_proposal',
                       'workflow_start', 'workflow_advance', 'workflow_status',
                       'workflow_control', 'workflow_actions', 'workflow_waits']
    arguments: dict


class WorkflowView(Input):
    run_id: str


MODELS={'intake_start':Start,**{name:Session for name in ['intake_status','intake_advance','intake_inference','mapping_preview','workbench_view']},
    'intake_propose':Propose,'intake_propose_sources':ProposeSources,'mapping_apply':Apply,
    'intake_dispose':Dispose,'intake_inherit':Inherit,'intake_extract':Extract,
    'ontology_discovery_propose':DiscoveryPropose,'ontology_registry':Registry,
    'ontology_publish_prepare':PublishPrepare,'ontology_publish_confirm':PublishConfirm,
    'ontology_query':OntologyQuery,'ontology_instances_summary':OntologyInstancesSummary,
    'source_connections':SourceConnections,
    'workflow_call':WorkflowCall,'workflow_view':WorkflowView}
# Read-only tools carry the MCP annotation so a host can show them as safe.
READ_ONLY_TOOLS={'ontology_query','ontology_instances_summary'}
DESCRIPTIONS={'intake_start':'建立接入任务。陌生 SQLite 库用 mode=ontology_discovery 发现本体',
    'intake_advance':'探查来源并返回映射或本体发现所需的来源证据',
    'intake_inference':'读取经披露范围过滤的提案请求，含当前来源与任务修订',
    'intake_extract':'将已观察 PDF 的原文片段提取为有精确锚点的新字段',
    'intake_propose':'提交结构化映射；组件验证和试算，不直接发布',
    'intake_propose_sources':'按来源 ID 提交所有映射，一起验证并试算同一组本体对象',
    'mapping_preview':'读取当前预览修订、数量、问题摘要、冲突原值与可继承纠正',
    'mapping_apply':'对当前预览保存明确范围的决定；allow_partial=true 时放行无阻断对象并挂起其余对象，拒绝过期修订',
    'intake_dispose':'记录可审计的来源处置：标记分区不适用或排除某条记录，随后重新提交映射生成预览',
    'intake_inherit':'继承同一来源修订上旧任务仍有效的纠正，写入当前预览',
    'intake_status':'查询当前任务修订与阶段','workbench_view':'打开同一任务的本地工作台',
    'ontology_discovery_propose':'提交 SQLite 本体草案，验证来源键、字段和关系证据后供用户审核',
    'ontology_registry':'列出工作区内未停用本体注册表（只读）；include_deactivated=true 时包含已停用本体',
    'ontology_publish_prepare':'把发现草稿补全为多概念本体候选（值类型、必需性、身份、关系端点与未决处置）；只生成候选，不发布',
    'ontology_publish_confirm':'确认发布候选本体（仅工作台网页人工通道；Agent 调用只返回需要人工确认）',
    'ontology_query':'按本体与概念查询已发布实例（只读）：属性 eq/in/contains 过滤、分页，带来源定位、release_ref 与接入任务',
    'ontology_instances_summary':'汇总每个本体/概念的已发布实例数与最近发布时间（只读；默认不列停用本体）',
    'source_connections':'列出宿主已配置的来源连接名和类型（只读，不含凭据）',
    'workflow_call':'探查宿主配置的业务环境，提交、推进或查看已验证的流程和动作回执',
    'workflow_view':'在本地浏览器查看已登记工作流的执行状态'}
TOOLS=[{'name':name,'description':DESCRIPTIONS[name],
        'inputSchema':model.model_json_schema(),
        **({'annotations':{'readOnlyHint':True}} if name in READ_ONLY_TOOLS else {})}
       for name,model in MODELS.items()]
