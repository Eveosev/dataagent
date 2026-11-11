import {compile} from 'json-schema-to-typescript';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
const target=new URL('../src/generated/',import.meta.url);await mkdir(target,{recursive:true});
for(const [namespace,name] of [['intake','SourceProfile'],['intake','IntakeSession'],['ontology','OntologyRevision'],['ontology','MappingSpec'],['ontology','MappingPreview']]){
 const schema=JSON.parse(await readFile(new URL(`../../../dataagent-contracts/schema/generated/${namespace}.${name}.json`,import.meta.url),'utf8'));
 const code=await compile(schema,name,{bannerComment:'/* Generated from dataagent-contracts. Do not edit. */'});
 await writeFile(new URL(`${name}.ts`,target),code);
}
