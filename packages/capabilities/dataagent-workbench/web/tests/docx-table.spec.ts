import {test,expect} from '@playwright/test';
import {awaitProbed,pinBuiltinOntology,slowTimeout} from './support';

// 最小可解析的合成 Word 登记表：首尾各一段，中间一张 3×4 表（表头 + 2 行数据）。
// 数据层探查默认选 table:1 记录集，单元格锚点 unit_ref = table:1/row:r/col:c。
const docx=Buffer.from(
 'UEsDBBQAAAAIAPqLcl0CxKfs2AAAAEsBAAATAAAAW0NvbnRlbnRfVHlwZXNdLnhtbH2QzU4DMQyEXyXKFe1m4YAQ'
+'2mwP/ByBQ3kAK/FuoyZOlLilfXu8FPXAgaP9zYxHHjenFNURawuZrL7tB62QXPaBFqs/t6/dg1aNgTzETGj1GZveT'
+'OP2XLAp8VKzesdcHo1pbocJWp8LkpA51wQsY11MAbeHBc3dMNwbl4mRuOM1Q0/jM85wiKxeTrK+9BC7Vk8X3XrKai'
+'glBgcs2KzUTOO71K7Bo/qAym+QRGW+cvXGZ3dI4uz/jzmS/9O1y/McHF79a1qp2WFr8o8U+ytJEOjmt4f5ecb0DVBL'
+'AwQUAAAACAD6i3Jdm/036q0AAAApAQAACwAAAF9yZWxzLy5yZWxzjc87DsIwDAbgq0TeaVoGhFDTLgipKyoHsBI3rW'
+'geSsKjtycDA0UMjLZ/f5br9mlmdqcQJ2cFVEUJjKx0arJawKU/bfbAYkKrcHaWBCwUoW3qM82Y8kocJx9ZNmwUMKbk'
+'D5xHOZLBWDhPNk8GFwymXAbNPcorauLbstzx8GnA2mSdEhA6VQHrF0//2G4YJklHJ2+GbPpx4iuRZQyakoCHC4qrd7'
+'vILPCm5qsXmxdQSwMEFAAAAAgA+otyXbCY8depAQAAwgYAABEAAAB3b3JkL2RvY3VtZW50LnhtbN1VS0sDMRD+K0vu'
+'NmkPoqVbD4LiRQRfeEx3Y13YTZYka92bCKL4rAefqFBQ7KGoIIKo4I/R3fbmXzBpq1YQPeh68DIzmcx8X2YmJLm+Oc8'
+'1ZgkXDqMmSKcQMAi1mO3QognGxwa6eoAhJKY2dhklJgiJAH35XClrMyvwCJWGAqAiWzLBjJR+FkJhzRAPixTzCVV70'
+'4x7WKolL8IS47bPmUWEUPieCzMIdUMPOxRoyAKzQ619LbgWMh9tbtVPq/X9u8b5ZaNSzUHt1JI3ZTNUFty2GuFtY1SG'
+'LjFK2VnsmmAMF1wyyB0bwGZSZ6B2a7OodD9zVYqqRB0L6dhfccMPPLJFbLVk+xjWZEeKMmXoq1bbc/g1vx3Y2RgaeAX'
+'CP+kHfIf/MQn2WEBlwiRWwLm6c2HCNI4QwVcNg2/D+a0RDQ1PdCGUTriudKYbpRBKmKV/eCphhmh94+mhEq0cR4u1v5'
+'9SJuHqetH/GNLabry3UT/bilfmvx0SfHuaP0CcLMVX1ef7g/iwpl70p5vbqLwcL5fj69XGxXZ8VI539h/nFz5Hb30R8'
+'P37yb8AUEsBAhQDFAAAAAgA+otyXQLEp+zYAAAASwEAABMAAAAAAAAAAAAAAIABAAAAAFtDb250ZW50X1R5cGVzXS54'
+'bWxQSwECFAMUAAAACAD6i3Jdm/036q0AAAApAQAACwAAAAAAAAAAAAAAgAEJAQAAX3JlbHMvLnJlbHNQSwECFAMUAAA'
+'ACAD6i3JdsJjx16kBAADCBgAAEQAAAAAAAAAAAAAAgAHfAQAAd29yZC9kb2N1bWVudC54bWxQSwUGAAAAAAMAAwC5AA'
+'AAtwMAAAAA','base64');

test('上传框接受 Word 文件并在提示中列出 Word（FDE-7）',async({page})=>{
 await page.goto('/');
 await expect(page.getByLabel('选择材料')).toHaveAttribute('accept',/\.docx/);
 await expect(page.getByText('PDF、Excel、Word、CSV、JSON、SQLite')).toBeVisible();
});

test('Word 表格单元格定位显示表与行列而不是字符偏移（G4）',async({page})=>{
 slowTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入 Word 发票登记表并核对表格定位');
 await page.getByLabel('选择材料').setInputFiles({name:'发票登记表.docx',
  mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:docx});
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await awaitProbed(page);
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByTestId('object-number')).toHaveText('INV-001');
 // 表头被识别为列名：字段直接可用，段落没有混成对象。
 await expect(page.locator('.source-tab')).toHaveCount(2);
 // 每个值的来源定位都是「表 t 第 r 行 · 列名」，不再是字符偏移。
 await expect(page.getByText('发票登记表.docx · 表 1 第 2 行 · 单据编号').first()).toBeVisible();
 await expect(page.getByText('发票登记表.docx · 表 1 第 2 行 · 开票方').first()).toBeVisible();
 await expect(page.getByText(/字符 0–/)).toHaveCount(0);
 await page.getByRole('button',{name:/INV-002/}).click();
 await expect(page.getByText('发票登记表.docx · 表 1 第 3 行 · 单据编号').first()).toBeVisible();
});
