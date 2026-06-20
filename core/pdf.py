from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

def money(value):
    return "Rp " + f"{value:,.0f}".replace(",", ".")

def html(value):
    return escape(str(value or "")).replace("\n","<br/>")

def build_invoice_pdf(invoice, company):
    output=BytesIO()
    doc=SimpleDocTemplate(output,pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=15*mm,bottomMargin=15*mm,title=invoice.number)
    styles=getSampleStyleSheet()
    base=ParagraphStyle("CJK",parent=styles["BodyText"],fontName="STSong-Light",fontSize=9,leading=13,textColor=colors.HexColor("#4f5662"))
    heading=ParagraphStyle("Heading",parent=base,fontSize=16,leading=20,textColor=colors.HexColor("#18212f"))
    title=ParagraphStyle("Title",parent=base,fontSize=28,leading=32,textColor=colors.HexColor("#6956e8"),alignment=TA_RIGHT)
    right=ParagraphStyle("Right",parent=base,alignment=TA_RIGHT)
    story=[]
    identity=[]
    if company.logo:
        try: identity.append(Image(company.logo.path,width=32*mm,height=22*mm))
        except Exception: pass
    company_text=f"<b>{html(company.name)}</b><br/>{html(company.address)}<br/>{html(company.phone)} · {html(company.email)}<br/>{html(company.website)}"
    if company.npwp: company_text += f"<br/>NPWP: {html(company.npwp)}"
    identity.append(Paragraph(company_text,base))
    company_block=Table([identity],colWidths=[34*mm,None]) if company.logo else identity[0]
    invoice_block=[Paragraph("INVOICE",title),Paragraph(f"<b>{invoice.number}</b><br/>{invoice.get_status_display()}",right)]
    story.append(Table([[company_block,invoice_block]],colWidths=[112*mm,55*mm],style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")])) )
    story.append(Spacer(1,10*mm))
    customer=f"<font color='#777777'>Bill to / 账单客户 / Ditagihkan kepada</font><br/><b>{html(invoice.customer.name)}</b><br/>{html(invoice.customer.address)}"
    if invoice.customer.npwp: customer += f"<br/>NPWP: {html(invoice.customer.npwp)}"
    dates=f"Issue date: <b>{invoice.issue_date}</b><br/>Due date: <b>{invoice.due_date}</b>"
    story.append(Table([[Paragraph(customer,base),Paragraph(dates,right)]],colWidths=[112*mm,55*mm],style=TableStyle([("LINEABOVE",(0,0),(-1,0),0.5,colors.HexColor("#dddddd")),("TOPPADDING",(0,0),(-1,0),8*mm),("VALIGN",(0,0),(-1,-1),"TOP")])) )
    story.append(Spacer(1,7*mm))
    data=[[Paragraph("Description",base),Paragraph("Qty",right),Paragraph("Price",right),Paragraph("Amount",right)]]
    for item in invoice.items.all(): data.append([Paragraph(html(item.description),base),Paragraph(str(item.quantity),right),Paragraph(money(item.unit_price),right),Paragraph(money(item.total),right)])
    items=Table(data,colWidths=[83*mm,20*mm,32*mm,32*mm],repeatRows=1)
    items.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2b2d42")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,-1),"STSong-Light"),("BOTTOMPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),8),("LINEBELOW",(0,1),(-1,-1),0.4,colors.HexColor("#dddddd")),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(items); story.append(Spacer(1,7*mm))
    payment=Paragraph(f"<font color='#777777'>Payment / 付款 / Pembayaran</font><br/>{html(company.bank_details)}<br/><br/>{html(invoice.notes)}",base)
    totals=[["Subtotal",money(invoice.subtotal)],["Discount",money(invoice.discount)],[f"PPN {invoice.tax_rate}%",money(invoice.tax)],["TOTAL",money(invoice.total)],["Paid",money(invoice.paid)],["Balance",money(invoice.balance)]]
    totals_table=Table(totals,colWidths=[31*mm,39*mm],style=[("FONTNAME",(0,0),(-1,-1),"STSong-Light"),("ALIGN",(1,0),(1,-1),"RIGHT"),("BACKGROUND",(0,3),(-1,3),colors.HexColor("#f1efff")),("TEXTCOLOR",(0,3),(-1,3),colors.HexColor("#6956e8")),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),("LINEABOVE",(0,5),(-1,5),0.5,colors.HexColor("#aaaaaa"))])
    story.append(Table([[payment,totals_table]],colWidths=[97*mm,70*mm],style=[("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(Spacer(1,15*mm)); story.append(Paragraph("Thank you for your business · 感谢惠顾 · Terima kasih",ParagraphStyle("Footer",parent=base,alignment=1)))
    doc.build(story)
    return output.getvalue()
