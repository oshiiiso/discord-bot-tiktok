import discord
from services.streamers import load_streamers


def get_role(guild, role_id):
    return guild.get_role(int(role_id))


class StreamerButton(discord.ui.Button):
    def __init__(self, label: str, role_id: str):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):

        role = get_role(interaction.guild, self.role_id)

        if role is None:
            await interaction.response.send_message("ロールが見つかりません", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
        else:
            await interaction.user.add_roles(role)

        # 最新状態を取り直す
        member = await interaction.guild.fetch_member(interaction.user.id)

        await interaction.response.edit_message(
            view=create_view(interaction.guild, member)
        )


class StreamerView(discord.ui.View):
    def __init__(self, guild: discord.Guild, user: discord.Member):
        super().__init__(timeout=120)

        self.streamers = load_streamers()

        for s in self.streamers:
            role = get_role(guild, s["role_id"])

            is_on = role in user.roles if role else False

            style = (
                discord.ButtonStyle.success
                if is_on
                else discord.ButtonStyle.danger
            )

            button = StreamerButton(s["label"], s["role_id"])
            button.style = style

            self.add_item(button)


def create_view(guild, user):
    return StreamerView(guild, user)
