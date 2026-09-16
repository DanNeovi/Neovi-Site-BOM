import fs from 'node:fs/promises';
import {loadTemplateConfig} from '../src/template-model.mjs';
const {lines} = await loadTemplateConfig();
await fs.mkdir('outputs/NeoviBOM/_Internal/Model-Data',{recursive:true});
await fs.writeFile('outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json',JSON.stringify(lines,null,2));
