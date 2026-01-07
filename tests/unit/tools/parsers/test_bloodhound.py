"""Comprehensive unit tests for bloodhound parser - 100% coverage."""
import pytest
import uuid
from cyberred.tools.parsers import bloodhound


@pytest.fixture
def agent_id():
    return str(uuid.uuid4())


@pytest.mark.unit
class TestBloodhoundParserSignature:
    """Test parser signature and basic functionality."""
    
    def test_bloodhound_parser_signature(self, agent_id):
        """Test parser is callable with correct signature."""
        assert callable(bloodhound.bloodhound_parser)
        result = bloodhound.bloodhound_parser(stdout='', stderr='', exit_code=0, agent_id=agent_id, target="corp.local")
        assert isinstance(result, list)
    
    def test_empty_stdout(self, agent_id):
        """Test empty stdout returns empty list."""
        result = bloodhound.bloodhound_parser('', '', 0, agent_id, "corp.local")
        assert result == []
    
    def test_whitespace_only_stdout(self, agent_id):
        """Test whitespace-only stdout returns empty list."""
        result = bloodhound.bloodhound_parser('   \n\t  ', '', 0, agent_id, "corp.local")
        assert result == []
    
    def test_invalid_json(self, agent_id):
        """Test invalid JSON returns empty list."""
        result = bloodhound.bloodhound_parser('not valid json {{{', '', 0, agent_id, "corp.local")
        assert result == []


@pytest.mark.unit
class TestBloodhoundDictFormat:
    """Test BloodHound dict format with data/meta keys."""
    
    def test_data_key_with_meta_type(self, agent_id):
        """Test parsing with data key and meta type."""
        stdout = '''{
            "data": [{"Properties": {"name": "ADMIN@CORP.LOCAL", "highvalue": true}}],
            "meta": {"type": "users", "count": 1}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1
        assert findings[0].type == "ad_object"
        assert "ADMIN@CORP.LOCAL" in findings[0].evidence
    
    def test_users_key_without_meta(self, agent_id):
        """Test parsing with users key when no meta type provided."""
        stdout = '''{
            "users": [
                {"Properties": {"name": "USER1@CORP.LOCAL"}},
                {"Properties": {"name": "USER2@CORP.LOCAL"}}
            ]
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 2
    
    def test_computers_key_without_meta(self, agent_id):
        """Test parsing with computers key when no meta type provided."""
        stdout = '''{
            "computers": [
                {"Properties": {"name": "DC01.CORP.LOCAL"}},
                {"Properties": {"name": "SERVER01.CORP.LOCAL"}}
            ]
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 2
        assert any("DC01" in f.evidence for f in findings)
    
    def test_groups_key_without_meta(self, agent_id):
        """Test parsing with groups key when no meta type provided."""
        stdout = '''{
            "groups": [
                {"Properties": {"name": "DOMAIN ADMINS@CORP.LOCAL"}},
                {"Properties": {"name": "USERS@CORP.LOCAL"}}
            ]
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 2
    
    def test_fallback_to_data_key_items(self, agent_id):
        """Test fallback to data key when no specific type key exists."""
        stdout = '''{
            "data": [{"Properties": {"name": "ITEM@CORP.LOCAL"}}]
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1


@pytest.mark.unit
class TestBloodhoundListFormat:
    """Test BloodHound list format (array of objects)."""
    
    def test_list_format_basic(self, agent_id):
        """Test parsing list format."""
        stdout = '''[
            {"Properties": {"name": "ADMIN@CORP.LOCAL", "highvalue": true}, "ObjectType": "User"},
            {"Properties": {"name": "GUEST@CORP.LOCAL"}, "ObjectType": "User"}
        ]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 2
    
    def test_list_format_with_type_in_properties(self, agent_id):
        """Test list format with type in properties."""
        stdout = '''[
            {"Properties": {"name": "DC01@CORP.LOCAL", "type": "Computer"}}
        ]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1
    
    def test_list_format_empty_array(self, agent_id):
        """Test empty list returns empty findings."""
        stdout = '[]'
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 0


@pytest.mark.unit
class TestBloodhoundHighValueDetection:
    """Test high-value target detection."""
    
    def test_domain_admins_high_value(self, agent_id):
        """Test Domain Admins group is flagged as high value."""
        stdout = '''{
            "data": [{"Properties": {"name": "DOMAIN ADMINS@CORP.LOCAL"}}],
            "meta": {"type": "groups"}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1
        assert findings[0].severity == "high"
        assert "[HIGH VALUE]" in findings[0].evidence
    
    def test_enterprise_admins_high_value(self, agent_id):
        """Test Enterprise Admins group is flagged as high value."""
        stdout = '''{
            "data": [{"Properties": {"name": "ENTERPRISE ADMINS@CORP.LOCAL"}}],
            "meta": {"type": "groups"}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert findings[0].severity == "high"
    
    def test_administrators_high_value(self, agent_id):
        """Test Administrators group is flagged as high value."""
        stdout = '''{
            "data": [{"Properties": {"name": "ADMINISTRATORS@CORP.LOCAL"}}],
            "meta": {"type": "group"}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert findings[0].severity == "high"
    
    def test_schema_admins_high_value(self, agent_id):
        """Test Schema Admins group is flagged as high value."""
        stdout = '''{
            "data": [{"Properties": {"name": "SCHEMA ADMINS@CORP.LOCAL"}}],
            "meta": {"type": "groups"}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert findings[0].severity == "high"
    
    def test_highvalue_property_true(self, agent_id):
        """Test highvalue property sets high severity."""
        stdout = '''{
            "data": [{"Properties": {"name": "SVC_BACKUP@CORP.LOCAL", "highvalue": true}}],
            "meta": {"type": "users"}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert findings[0].severity == "high"
        assert "[HIGH VALUE]" in findings[0].evidence
    
    def test_admincount_property(self, agent_id):
        """Test admincount > 0 sets high severity."""
        stdout = '''{
            "data": [{"Properties": {"name": "ADMIN@CORP.LOCAL", "admincount": 1}}],
            "meta": {"type": "users"}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert findings[0].severity == "high"
    
    def test_regular_user_info_severity(self, agent_id):
        """Test regular user has info severity."""
        stdout = '''{
            "data": [{"Properties": {"name": "JSMITH@CORP.LOCAL", "highvalue": false, "admincount": 0}}],
            "meta": {"type": "users"}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert findings[0].severity == "info"
        assert "[HIGH VALUE]" not in findings[0].evidence


@pytest.mark.unit
class TestBloodhoundPropertyAccess:
    """Test different property access patterns."""
    
    def test_properties_key_access(self, agent_id):
        """Test accessing name via Properties key."""
        stdout = '''[{"Properties": {"name": "TEST@CORP.LOCAL"}, "ObjectType": "User"}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1
        assert "TEST@CORP.LOCAL" in findings[0].evidence
    
    def test_direct_properties_access(self, agent_id):
        """Test accessing name directly when no Properties key."""
        stdout = '''[{"name": "DIRECT@CORP.LOCAL", "ObjectType": "User"}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1
        assert "DIRECT@CORP.LOCAL" in findings[0].evidence
    
    def test_samaccountname_fallback(self, agent_id):
        """Test falling back to samaccountname when name not present."""
        stdout = '''{
            "data": [{"Properties": {"samaccountname": "svc_account"}}],
            "meta": {"type": "users"}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1
        assert "svc_account" in findings[0].evidence
    
    def test_empty_name_skipped(self, agent_id):
        """Test items with empty name are skipped."""
        stdout = '''{
            "data": [
                {"Properties": {"name": ""}},
                {"Properties": {"name": "VALID@CORP.LOCAL"}}
            ],
            "meta": {"type": "users"}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1
        assert "VALID@CORP.LOCAL" in findings[0].evidence
    
    def test_missing_name_skipped(self, agent_id):
        """Test items without name or samaccountname are skipped."""
        stdout = '''{
            "data": [
                {"Properties": {"description": "No name here"}},
                {"Properties": {"name": "HAS_NAME@CORP.LOCAL"}}
            ],
            "meta": {"type": "users"}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1


@pytest.mark.unit
class TestBloodhoundListItemParsing:
    """Test _parse_bloodhound_item function via list format."""
    
    def test_item_with_object_type(self, agent_id):
        """Test parsing item with ObjectType field."""
        stdout = '''[{"Properties": {"name": "DC01@CORP.LOCAL"}, "ObjectType": "Computer"}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1
        assert "Computer" in findings[0].evidence
    
    def test_item_with_type_in_properties(self, agent_id):
        """Test parsing item with type in Properties."""
        stdout = '''[{"Properties": {"name": "USER@CORP.LOCAL", "type": "User"}}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1
        assert "User" in findings[0].evidence
    
    def test_item_default_object_type(self, agent_id):
        """Test default object type when none specified."""
        stdout = '''[{"Properties": {"name": "UNKNOWN@CORP.LOCAL"}}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 1
        assert "object" in findings[0].evidence.lower()
    
    def test_item_highvalue_in_list_format(self, agent_id):
        """Test highvalue detection in list format."""
        stdout = '''[{"Properties": {"name": "ADMIN@CORP.LOCAL", "highvalue": true}, "ObjectType": "User"}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert findings[0].severity == "high"
    
    def test_item_admincount_in_list_format(self, agent_id):
        """Test admincount detection in list format."""
        stdout = '''[{"Properties": {"name": "ADMIN@CORP.LOCAL", "admincount": 1}, "ObjectType": "User"}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert findings[0].severity == "high"
    
    def test_item_no_name_returns_empty(self, agent_id):
        """Test item without name returns empty list."""
        stdout = '''[{"Properties": {"description": "No name"}, "ObjectType": "User"}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 0


@pytest.mark.unit
class TestBloodhoundEdgeCases:
    """Test edge cases and error handling."""
    
    def test_non_dict_items_in_list(self, agent_id):
        """Test handling of non-dict items in data list."""
        stdout = '''{
            "data": ["string_item", {"Properties": {"name": "VALID@CORP.LOCAL"}}],
            "meta": {"type": "users"}
        }'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        # Should only process the valid dict item
        assert len(findings) == 1
    
    def test_nested_empty_properties(self, agent_id):
        """Test handling of empty Properties dict."""
        stdout = '''[{"Properties": {}, "ObjectType": "User"}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert len(findings) == 0
    
    def test_tool_name_in_findings(self, agent_id):
        """Test that tool name is correctly set."""
        stdout = '''[{"Properties": {"name": "TEST@CORP.LOCAL"}, "ObjectType": "User"}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert findings[0].tool == "bloodhound"
    
    def test_finding_type_is_ad_object(self, agent_id):
        """Test that finding type is ad_object."""
        stdout = '''[{"Properties": {"name": "TEST@CORP.LOCAL"}, "ObjectType": "User"}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert findings[0].type == "ad_object"
    
    def test_target_in_findings(self, agent_id):
        """Test that target is correctly set."""
        stdout = '''[{"Properties": {"name": "TEST@CORP.LOCAL"}, "ObjectType": "User"}]'''
        findings = bloodhound.bloodhound_parser(stdout, '', 0, agent_id, "corp.local")
        assert findings[0].target == "corp.local"
