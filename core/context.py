def company_context(request):
    membership = None
    if request.user.is_authenticated:
        membership = request.user.memberships.filter(active=True).select_related("company").first()
    return {"membership": membership, "company": membership.company if membership else None}
