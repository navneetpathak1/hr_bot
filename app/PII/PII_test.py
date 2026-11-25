from . import imports_PII


result = imports_PII.redact_pii("Hello my name is Navneet, ABC!123afd@@@@@#")

result2 = imports_PII.extract_pii("Hello my name is")
print(result)
print(result2)

