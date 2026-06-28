from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

def _register_invoice_font():
    candidates = [
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
        ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 0),
        ("/System/Library/Fonts/STHeiti Light.ttc", 0),
        ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
        ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
    ]
    for path, subfont_index in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("InvoiceHubFont", path, subfontIndex=subfont_index))
                return "InvoiceHubFont"
            except Exception:
                continue
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:
        return "Helvetica"

PDF_FONT = _register_invoice_font()

def money(value):
    return "Rp " + f"{value:,.0f}".replace(",", ".")

def number(value):
    try:
        if value == value.to_integral():
            return f"{value:,.0f}".replace(",", ".")
    except Exception:
        pass
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

def html(value):
    return escape(str(value or "")).replace("\n","<br/>")

def build_invoice_pdf(invoice, company):
    output=BytesIO()
    doc=SimpleDocTemplate(output,pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=15*mm,bottomMargin=15*mm,title=invoice.number)
    styles=getSampleStyleSheet()
    base=ParagraphStyle("CJK",parent=styles["BodyText"],fontName=PDF_FONT,fontSize=9,leading=13,textColor=colors.HexColor("#4f5662"))
    small=ParagraphStyle("Small",parent=base,fontSize=8,leading=11,textColor=colors.HexColor("#77808f"))
    heading=ParagraphStyle("Heading",parent=base,fontSize=16,leading=20,textColor=colors.HexColor("#18212f"))
    title=ParagraphStyle("Title",parent=base,fontSize=30,leading=34,textColor=colors.HexColor("#2b2d42"),alignment=TA_RIGHT)
    label=ParagraphStyle("Label",parent=small,fontSize=7,leading=10,textColor=colors.HexColor("#77808f"))
    table_head=ParagraphStyle("TableHead",parent=base,textColor=colors.white)
    right=ParagraphStyle("Right",parent=base,alignment=TA_RIGHT)
    right_small=ParagraphStyle("RightSmall",parent=small,alignment=TA_RIGHT)
    right_head=ParagraphStyle("RightHead",parent=table_head,alignment=TA_RIGHT)
    center_small=ParagraphStyle("CenterSmall",parent=small,alignment=TA_CENTER)
    center_head=ParagraphStyle("CenterHead",parent=table_head,alignment=TA_CENTER)
    story=[]

    identity=[]
    if company.logo:
        try:
            identity.append(Image(company.logo.path,width=28*mm,height=20*mm))
        except Exception:
            pass
    company_text=f"<b>{html(company.name)}</b>"
    if company.address: company_text += f"<br/>{html(company.address)}"
    contact = " · ".join([html(x) for x in [company.phone, company.email] if x])
    if contact: company_text += f"<br/>{contact}"
    if company.website: company_text += f"<br/>{html(company.website)}"
    if company.npwp: company_text += f"<br/>NPWP: {html(company.npwp)}"
    identity.append(Paragraph(company_text,base))
    company_block=Table([identity],colWidths=[30*mm,78*mm],style=[("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]) if len(identity)>1 else identity[0]
    invoice_block=[
        Paragraph("COMMERCIAL INVOICE",right_small),
        Paragraph("INVOICE",title),
        Paragraph(f"<b>{html(invoice.number)}</b><br/>{html(invoice.get_status_display())}",right),
    ]
    story.append(Table([[company_block,invoice_block]],colWidths=[112*mm,55*mm],style=TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LINEBELOW",(0,0),(-1,0),2,colors.HexColor("#2b2d42")),
        ("BOTTOMPADDING",(0,0),(-1,0),8*mm),
    ])))
    story.append(Spacer(1,8*mm))

    customer=f"<font color='#77808f'>Bill to / 账单客户 / Ditagihkan kepada</font><br/><b>{html(invoice.customer.name)}</b>"
    if invoice.customer.address: customer += f"<br/>{html(invoice.customer.address)}"
    if invoice.customer.email: customer += f"<br/>{html(invoice.customer.email)}"
    if invoice.customer.phone: customer += f"<br/>{html(invoice.customer.phone)}"
    if invoice.customer.npwp: customer += f"<br/>NPWP: {html(invoice.customer.npwp)}"
    dates=[
        [Paragraph("Issue date / 开票日期",label), Paragraph(str(invoice.issue_date),right)],
        [Paragraph("Due date / 到期日",label), Paragraph(str(invoice.due_date),right)],
        [Paragraph("Currency / 币种",label), Paragraph(html(company.currency or "IDR"),right)],
    ]
    dates_table=Table(dates,colWidths=[28*mm,22*mm],style=[
        ("FONTNAME",(0,0),(-1,-1),PDF_FONT),
        ("LINEBELOW",(0,0),(-1,-2),0.4,colors.HexColor("#e6e8ef")),
        ("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ])
    story.append(Table([[Paragraph(customer,base),dates_table]],colWidths=[99*mm,68*mm],style=TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#f8f9fc")),
        ("BOX",(0,0),(-1,-1),0.6,colors.HexColor("#e6e8ef")),
        ("INNERGRID",(0,0),(-1,-1),0.6,colors.HexColor("#e6e8ef")),
        ("LEFTPADDING",(0,0),(-1,-1),8*mm),
        ("RIGHTPADDING",(0,0),(-1,-1),8*mm),
        ("TOPPADDING",(0,0),(-1,-1),6*mm),
        ("BOTTOMPADDING",(0,0),(-1,-1),6*mm),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ])))
    story.append(Spacer(1,8*mm))

    data=[[
        Paragraph("#",center_head),
        Paragraph("Description / 明细 / Deskripsi",table_head),
        Paragraph("Qty",right_head),
        Paragraph("Unit price",right_head),
        Paragraph("Amount",right_head),
    ]]
    for index, item in enumerate(invoice.items.all(), 1):
        data.append([
            Paragraph(str(index),center_small),
            Paragraph(html(item.description),base),
            Paragraph(number(item.quantity),right),
            Paragraph(money(item.unit_price),right),
            Paragraph(money(item.total),right),
        ])
    items=Table(data,colWidths=[11*mm,72*mm,20*mm,32*mm,32*mm],repeatRows=1)
    items.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2b2d42")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,-1),PDF_FONT),
        ("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("TOPPADDING",(0,0),(-1,-1),8),
        ("LINEBELOW",(0,1),(-1,-1),0.4,colors.HexColor("#e6e8ef")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ALIGN",(2,1),(-1,-1),"RIGHT"),
        ("ALIGN",(0,0),(0,-1),"CENTER"),
    ]))
    story.append(items)
    story.append(Spacer(1,8*mm))

    payment_text = html(company.bank_details) if company.bank_details else "No payment information configured."
    if invoice.notes:
        payment_text += f"<br/><br/><font color='#77808f'>Notes / 备注 / Catatan</font><br/>{html(invoice.notes)}"
    payment=Paragraph(f"<font color='#77808f'>Payment information / 收款信息 / Informasi pembayaran</font><br/>{payment_text}",base)
    totals=[
        ["Subtotal",money(invoice.subtotal)],
        ["Discount",money(invoice.discount)],
    ]
    if company.show_ppn:
        totals.append([f"PPN {invoice.tax_rate}%", money(invoice.tax)])
    total_row = len(totals)
    paid_row = total_row + 1
    balance_row = total_row + 2
    totals.extend([
        ["TOTAL",money(invoice.total)],
        ["Paid",money(invoice.paid)],
        ["Balance",money(invoice.balance)],
    ])
    totals_table=Table(totals,colWidths=[31*mm,39*mm],style=[
        ("FONTNAME",(0,0),(-1,-1),PDF_FONT),
        ("ALIGN",(1,0),(1,-1),"RIGHT"),
        ("BACKGROUND",(0,total_row),(-1,total_row),colors.HexColor("#2b2d42")),
        ("TEXTCOLOR",(0,total_row),(-1,total_row),colors.white),
        ("BACKGROUND",(0,balance_row),(-1,balance_row),colors.HexColor("#f1efff")),
        ("TEXTCOLOR",(0,balance_row),(-1,balance_row),colors.HexColor("#6956e8")),
        ("BOX",(0,0),(-1,-1),0.6,colors.HexColor("#e6e8ef")),
        ("LINEBELOW",(0,0),(-1,-2),0.4,colors.HexColor("#e6e8ef")),
        ("TOPPADDING",(0,0),(-1,-1),7),
        ("BOTTOMPADDING",(0,0),(-1,-1),7),
    ])
    story.append(Table([[payment,totals_table]],colWidths=[97*mm,70*mm],style=[
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(0,0),0),
        ("RIGHTPADDING",(0,0),(0,0),10*mm),
        ("RIGHTPADDING",(1,0),(1,0),0),
    ]))
    story.append(Spacer(1,18*mm))
    signature=Table([
        ["","",""],
        [Paragraph("Prepared by / 制单 / Dibuat oleh",center_small), "", Paragraph("Authorized signature / 授权签名 / Tanda tangan",center_small)],
    ],colWidths=[62*mm,22*mm,62*mm],style=[
        ("LINEABOVE",(0,1),(0,1),0.6,colors.HexColor("#aeb4c0")),
        ("LINEABOVE",(2,1),(2,1),0.6,colors.HexColor("#aeb4c0")),
        ("TOPPADDING",(0,0),(-1,0),16*mm),
        ("TOPPADDING",(0,1),(-1,1),5),
        ("LEFTPADDING",(0,0),(-1,-1),0),
        ("RIGHTPADDING",(0,0),(-1,-1),0),
    ])
    story.append(signature)
    story.append(Spacer(1,8*mm))
    story.append(Paragraph("Thank you for your business. · 感谢惠顾 · Terima kasih",ParagraphStyle("Footer",parent=base,alignment=TA_CENTER,textColor=colors.HexColor("#77808f"))))
    doc.build(story)
    return output.getvalue()
