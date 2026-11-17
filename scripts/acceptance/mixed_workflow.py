"""Mixed workflow phase: the API workflow plus browser reconciliation."""

from . import api_workflow


def apply(report, project, args, context):
    report['workflow'] = api_workflow.verify(project, mixed=True)
